exclusiveprocess - Simple Cross-Process Locking in Python
=========================================================

This is a simple Python 3 module for ensuring that your code does not
execute concurrently in multiple processes, using POSIX file locking.

The lock can be acquired easily using ``with`` syntax or as a decorator.

Why?
----

If you have long-running processes that would cause corruption if it's
executed multiple times concurrently, this package is for you. You might
use this in scripts that make backups, perform database migrations, or
other long-running processes that need to abort if they are already
running.

How it works under the hood
---------------------------

The module uses POSIX file locking and a PID file:

-  A file is selected to hold lock information, typically
   ``/var/lock/py_exclusivelock_yournamehere.lock``, called the
   lockfile, based on a name you provide. The name is sanitized before
   being used in the filename.

-  If the lockfile already exists and it contains the PID of a running
   process (including the current process), then a ``CannotAcquireLock``
   exception is thrown.

-  Otherwise the lockfile is created (or overwritten) and this process's
   integer process ID is written to the file.

-  An exclusive lock is held on the file containing this Python module
   (``exclusiveprocess/__init__.py``) during the above to prevent race
   conditions.

-  The lockfile is deleted when the ``with`` block or decorated function
   exits. Or when used with ``.forever()`` (see below), at program exit.

How to use it
-------------

First install this package:

::

    pip3 install exclusiveprocess

Then in your Python file import the package:

::

    from exclusiveprocess import Lock, CannotAcquireLock

You can use it in a ``with`` statement:

::

    try:
        with Lock(name="myprocess"):
            print("This block cannot be executed concurrently!")
    except CannotAcquireLock:
        print("Well, that's bad.")

Or as a decorator:

::

    @Lock(name="myprocess")
    def myfunc():
        print("This function cannot be executed concurrently!")

The ``name`` is up to you. The lock is specific to the name. The name is
system global (as global as the file system).

There are also some handy features for locking your whole program.

1. The ``name`` argument is optional and defaults to the filename of the
   module that contains the function that called ``Lock`` (i.e. your
   Python source file), using
   `inspect.stack() <https://docs.python.org/3.5/library/inspect.html#inspect.stack>`__,
   which results in the Lock being automatically exclusive to all
   invoations of your application.

2. When you set the optional ``die`` keyword argument to ``True``,
   ``Lock`` will print an error to STDERR and exit the process
   immediately with exit code 1 if the lock cannot be acquired, instead
   of rasing an exception.

3. The lock can be acquired with ``.forever()``, instead of ``with`` and
   decorator syntax, in which case the lock will be released only at
   program exit using
   `atexit <https://docs.python.org/3.5/library/atexit.html>`__.

With these features, you can make your whole program exclusive by
placing the following line at the start of your program:

::

    # At program start.
    Lock(die=True).forever()
    # program exits here if lock could not be acquired

If two such programs are run conncurrently you will see on STDERR:

::

    Another '/home/user/your_script.py' process is already running (pid 27922).

Advanced
--------

The ``with`` object can be captured if you want to see where the
lockfile is stored:

::

    with Lock(name="test1") as lock:
        print(lock.lockfile)

    # outputs:
    /var/lock/py_exclusivelock_test1.lock

The ``Lock`` class logs every lock acquired and released to
``logging.info``.
