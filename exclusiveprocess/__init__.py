import atexit
import errno
import inspect
import os
import os.path
import sys
import tempfile
import urllib.parse
import logging


class CannotAcquireLock(Exception):
    pass


class Lock(object):
    """Create a system-wide exclusive lock for a given global name."""

    def __init__(self, *args, name=None, die=False):
        """Creates a new Lock with a global name, or raises
        CannotAcquireLock if the name is already in use by
        another Lock instance possibly in another process.
        If name isn't given, one is automatically generated
        from the filename of the calling function. If die
        is set to True, then if the lock cannot be acquired
        a message is written to STDERR and the process exits
        with exit code 1."""

        if name is None:
            # Use the name of the file containing the calling
            # function.
            name = os.path.abspath(inspect.stack()[1].filename)

        self.name = name
        self.die = die

        # Is this being used as a decorator? Yes if it's one
        # argument is a function.
        self.decorated_function = None
        if len(args) == 1:
            if isinstance(args[0], str):
                raise ValueError("Don't pass the lock name as a positional argument -- use the name keyword argument.")
            if callable(args[0]):
                self.decorated_function = args[0]

    def __enter__(self):
        # Supports the "with" statement. The return value doesn't
        # matter since "with new Lock() as x" isn't really meaningful.
        self._acquire()
        return self

    def __exit__(self, *exc_info):
        # Called at the end of the "with" statement.
        self._release()

    def __call__(self, *args, **kwargs):
        if not self.decorated_function:
            raise TypeError("Lock object does not support __call__ except when used as a decorator.")
        with self:
            return self.decorated_function(*args, **kwargs)

    def forever(self):
        # Holds the lock for the lifetime of the Python process.
        # This method doesn't actually do anything except schedule
        # a cleanup routine that executes when the Python process
        # exits. If the Python process exits without the cleanup
        # routine being excuted, that's totally fine, but it's
        # nice to remove the lockfile.
        self._acquire()
        atexit.register(self._release)

    def _acquire(self):
        self.lockfile = get_lock_file(self.name)
        my_pid = str(os.getpid())

        # First get an exclusive lock on the file that holds this Python
        # module, so that we can assume there won't be any race conditions
        # within the following code.
        with open(__file__, 'r+') as flock:
            # Try to get a lock. This blocks until a lock is acquired. The
            # lock is held until the flock file is closed at the end of the
            # with block.
            os.lockf(flock.fileno(), os.F_LOCK, 0)

            # Write our process ID to the lockfile, if the lockfile doesn't
            # yet exist.
            try:
                with open(self.lockfile, 'x') as f:
                    # Successfully opened a new file. Since the file is new
                    # there is no concurrent process. Write our pid.
                    f.write(my_pid)

            except FileExistsError:
                # The lockfile already exixts, which probably indicates
                # another process is running and is holding the lock.
                # But it may contain a stale pid of a terminated process.
                # Try to open the lockfile again, but this time with
                # read+write access.
                with open(self.lockfile, 'r+') as f:
                    # Read the pid in the file.
                    try:
                        existing_pid = int(f.read().strip())
                    except ValueError:
                        # The contents of the lockfile are not valid.
                        pass
                    else:
                        # Check if the pid in it is valid, and if so, the
                        # lock is held by another process and this Lock
                        # cannot be created.
                        if is_pid_valid(existing_pid):
                            msg = "Another '%s' process is already running (pid %d)." % (self.name, existing_pid)
                            if not self.die:
                                raise CannotAcquireLock(msg)
                            else:
                                print(msg, file=sys.stderr)
                                sys.exit(1)

                    # The file didn't have a valid pid, so overwrite the file
                    # with our pid.
                    f.seek(0)
                    f.write(my_pid)
                    f.truncate()

            # Log success. Can't do this before the open since we expect
            # it to fail sometimes.
            logging.info("Acquired lock at " + self.lockfile + "...")

    def _release(self):
        """Release the lock by deleting the lockfile."""
        try:
            os.unlink(self.lockfile)

            # Log success. Can't do this before the open since we expect
            # it to fail sometimes.
            logging.info("Released lock at " + self.lockfile + "...")
        except:
            # Ignore all errors.
            pass


def get_lock_file(name):
    """Gets the file name to use to store the lock. If /var/lock is
       a directory, lock files are stored there. Otherwise they are
       stored in the system temporary directory, as returned by
       tempfile.gettempdir(). Any string may be given as the lock
       name, as it will be sanitized before being put into a file
       name."""

    # Sanitize the global lock name by using URL-style quoting, which
    # keeps most ASCII characters (nice) and turns the rest into ASCII.
    name = urllib.parse.quote_plus(name)

    # Add a global thing for ourself.
    name = "py_exclusivelock_" + name

    if os.path.isdir("/var/lock"):
        return "/var/lock/%s.lock" % name
    return os.path.join(tempfile.gettempdir(), name + ".pid")


def is_pid_valid(pid):
    """Checks whether a pid is a valid process ID of a currently running process."""
    # adapted from http://stackoverflow.com/questions/568271/how-to-check-if-there-exists-a-process-with-a-given-pid
    if not isinstance(pid, int) or pid <= 0: raise ValueError('Invalid PID.')
    try:
        os.kill(pid, 0)
    except OSError as err:
        if err.errno == errno.ESRCH: # No such process
            return False
        elif err.errno == errno.EPERM: # Not permitted to send signal
            return True
        else: # EINVAL
            raise
    else:
        return True

