# Log what happens so we can see that the locks are acquired and released.
import logging
logging.getLogger().setLevel('INFO')

# Begin tests...

from exclusiveprocess import Lock, CannotAcquireLock

# Try with a with block.

try:
	with Lock(name="test1") as lock:
		print("Hello!", lock.lockfile)
except CannotAcquireLock:
	raise ValueError("should not get here")

# Try with a with block, but choosing the lock name automatically.

try:
	with Lock() as lock:
		print("The lock name is based on the file path", lock.lockfile)
except CannotAcquireLock:
	raise ValueError("should not get here")

# Try with a decorator.

@Lock
def myfunc():
	print("This happened inside a lock with automatic lock name.")

myfunc()
myfunc()

@Lock(name="y")
def myfunc():
	print("This happened inside a lock with specified lock name.")

myfunc()
myfunc()

# Try different lock names, and with forever().

Lock(name="x").forever()
Lock(name="y").forever()

# Try default lock name, die=True, and forever().

Lock(die=True).forever()
Lock(die=True).forever()
raise Exception("should not get here")