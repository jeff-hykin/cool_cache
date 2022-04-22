# What is this?

The smart way to cache function outputs to permanent storage.

- auto rebuilds cache when you edit function source code
- uses mutltiprocessing to keep main thread running fast while saving to disk
- excellent argument change tracking thanks to `super_hash`
- even works for impure functions since external vars can be watched
- works well for class methods by picking parts of `self` to watch

# How do I use this?

`pip install cool_cache`

```python
from cool_cache import cache, settings

# this is the default, but you can change it
settings.default_folder="cache.ignore/"

# 
# simple usage (updates whenever function is edited (excluding comments) or when args change)
# 
@cache()
def things_with_args(a,b,c):
    
    from time import sleep; sleep(1) # <- simulating a long-running process
    
    return a + b + c

things_with_args(1,2,3) # not yet cached
things_with_args(1,2,3) # uses cache
things_with_args(9,9,9) # not yet cached
things_with_args(9,9,9) # uses cache


# 
# external vars
# 
external_counter = 0

@cache(depends_on=lambda:[external_counter])
def things_with_external(a,b,c):
    global external_counter
    
    from time import sleep; sleep(1) # <- simulating a long-running process
    
    return external_counter + a + b + c

# 
# example behavior
# 

things_with_external(4,5,6) # not yet cached
things_with_external(4,5,6) # uses cache
external_counter = 1
things_with_external(4,5,6) # not yet cached (because external_counter changed)
things_with_external(4,5,6) # uses cache


# 
# bust=True wipes out all cached values for this function on the next run
# 
@cache(bust=True)
def things(a,b,c):
    return 10
    
# 
# how to use cache with methods/self
# 
class MyThing:
    def __init__(self, path, other_stuff):
        self.path = path
        self.other_stuff = other_stuff
    
    # for example: self.path changing will affect the cache, but self.other_stuff wont affect the cache
    @cache(watch_attributes=lambda self:[ self.path, ])
    def do_some_stuff(self, arg1):
        from time import sleep; sleep(1)
        return self.path + arg1

```
