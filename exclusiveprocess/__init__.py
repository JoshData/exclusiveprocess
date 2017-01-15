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
            name = os.path.abspath(inspect.stack()[1][1])

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
        if self.decorated_function:
            # The Lock instance was initialized with a callable,
            # which is how it's used as a decorator like @Lock.
            # Execute the decorated function inside a lock.
            with self:
                return self.decorated_function(*args, **kwargs)
        elif len(args) == 1 and callable(args[0]):
            # An instantiated Lock object can be applied to a
            # function so enable @Lock(name="abc") syntax. In
            # this case, we're supposed to return a new decorated
            # function.
            return Lock(*args, name=self.name, die=self.die)
        else:
            raise TypeError("Lock object does not support __call__ except when used as a decorator.")

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

        # Write our process ID to the lockfile, if the lockfile doesn't
        # yet exist.
        try:
            with open(self.lockfile, 'x') as f:
                # Successfully opened a new file. Since the file is new
                # there is no concurrent process. Write our pid. Lock
                # first to prevent a race condition with the next block.
                os.lockf(f.fileno(), os.F_LOCK, 0)
                f.write(my_pid)

        except FileExistsError:
            # The lockfile already exists, or at least it did at the
            # moment we tried to open it above. That probably indicates
            # another process is running and is holding the lock.
            #
            # But it may contain a stale pid of a terminated process.
            #
            # And the file may have been deleted in a race condition.
            # In that case, an OSError will probably be raised, which
            # we'll re-wrap as a CannotAcquireLock.
            #
            # Open the lockfile in update ("r+") mode so we can check
            # the PID inside it and, if the PID is stale, write ours
            # to the file.
            try:
                with open(self.lockfile, 'r+') as f:
                    # Get an exclusive lock. This blocks until a lock is acquired. The
                    # lock is held until the flock file is closed at the end of the
                    # with block.
                    os.lockf(f.fileno(), os.F_LOCK, 0)

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

            except OSError as e:
                # There was a problem opening the existing lock file.
                raise CannotAcquireLock("There was an error opening %s after an open in 'x' mode failed, which might indicate the lock was held just moments ago: %s." % (self.lockfile, str(e)))

        # Log success. Can't do this before the open since we expect
        # it to fail sometimes.
        logging.info("Acquired lock at " + self.lockfile + "...")


    def _release(self):
        """Release the lock by deleting the lockfile."""
        try:
            os.unlink(self.lockfile)

            # Log success.
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

