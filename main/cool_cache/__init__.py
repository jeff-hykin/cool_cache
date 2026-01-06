# from: https://raw.githubusercontent.com/andrewgazelka/smart-cache/master/smart_cache/__init__.py
# (MIT License on PyPi)
# has been modified to use super_hash and work on python3.8

from os import path
from copy import deepcopy
import time

from .__dependencies__ import file_system_py as FS
from .__dependencies__.super_hash import super_hash, hash_file

# TODO:
    # create a class based system as an alternaitve to global settings
    # perform lightweight checks on list-likes (numpy, torch tensors, etc), by saving their shape and comparing shape before fully hashing what might be a giantic object (if shapes are different cache is instantly busted)

def get_pickle():
    pickle = None
    if settings.prefer_dill_over_pickle:
        try:
            # use dill if its available
            import dill as pickle
        except ImportError as error:
            import pickle
    else:
        import pickle
    
    return pickle

class Object:
    pass

class NotGiven:
    pass

settings = Object()
settings.default_folder = "cache.ignore/"
settings.worker_que_size = 1000
settings.prefer_dill_over_pickle = True

TIME_SUFFIXES_IN_SECONDS = {
    # m is milliseconds to keep the shorthand compact
    "m": 0.001,
    "s": 1,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    # 30d + 365d approximations are plenty accurate for cache busting
    "mo": 60 * 60 * 24 * 30,
    "y": 60 * 60 * 24 * 365,
}

class CacheData:
    calculated = False
    cache_file_name = ""
    deep_hash = ""
    cache = {}

# since we only care about latest
worker_que = None

def cache(folder=NotGiven, depends_on=lambda:None, watch_attributes=[], watch_filepaths=lambda *args, **kwargs:[], custom_hasher=None, bust=False, keep_for=None):
    global worker_que
    keep_for_seconds = parse_keep_for_seconds(keep_for)
    
    if folder == NotGiven:
        folder = settings.default_folder
    
    # save in ram
    if folder is None:
        def decorator_name(input_func):
            in_memory_cache = {}
            def wrapper(*args, **kwargs):
                hashed_args = list(args)
                # if watching attributes on self, replace first arg
                if callable(watch_attributes):
                    self = hashed_args[0]
                    hashed_args[0] = watch_attributes(self)
                    
                elif len(watch_attributes) > 0:
                    self = hashed_args[0]
                    attributes = {}
                    for each_attribute in watch_attributes:
                        if hasattr(self, each_attribute):
                            attributes[each_attribute] = getattr(self, each_attribute)
                    hashed_args[0] = attributes
                
                # 
                # filepath hashes
                # 
                filepaths_to_watch = watch_filepaths(*args, **kwargs)
                file_hashes = tuple(hash_file(each) for each in filepaths_to_watch)
                
                # 
                # custom_hasher
                # 
                if callable(custom_hasher):
                    hashed_args = custom_hasher(*args, **kwargs)
                    kwargs = None # need to exclude kwargs when custom_hasher is present
                
                # check if this arg combination has been used already
                arg_hash = super_hash((hashed_args, kwargs, depends_on(), file_hashes))
                if arg_hash in in_memory_cache:
                    cached_value, created_at = in_memory_cache[arg_hash]
                    if is_expired(keep_for_seconds, created_at):
                        in_memory_cache.pop(arg_hash, None)
                    else:
                        return cached_value
                # if args not in cache, run the function
                result = input_func(*args, **kwargs)
                in_memory_cache[arg_hash] = (time.time(), result)
                return result
            return wrapper
        return decorator_name
    
    # save in cold storage
    else:
        import queue
        import pickle
        import threading
        from threading import Thread
        if worker_que is None:
            worker_que = queue.Queue(maxsize=settings.worker_que_size)
            thread = Thread(target=worker)
            thread.start()
        def real_decorator(input_func):
            data = CacheData()
            function_id = super_hash(input_func)
            data.cache_file_name = f'cache.ignore/{function_id}.pickle'
            if bust:
                FS.remove(data.cache_file_name)
            def wrapper(*args, **kwargs):
                hashed_args = list(args)
                # if watching attributes on self, replace first arg
                if callable(watch_attributes):
                    self = hashed_args[0]
                    hashed_args[0] = watch_attributes(self)
                    
                elif len(watch_attributes) > 0:
                    self = hashed_args[0]
                    attributes = {}
                    for each_attribute in watch_attributes:
                        if hasattr(self, each_attribute):
                            attributes[each_attribute] = getattr(self, each_attribute)
                    hashed_args[0] = attributes
                
                # load cached values for this function
                if not data.calculated:
                    data.deep_hash = function_id
                    if path.exists(data.cache_file_name):
                        try:
                            with open(data.cache_file_name, 'rb') as cache_file:
                                func_hash, cache_temp = get_pickle().load(cache_file)
                                if func_hash == data.deep_hash:
                                    data.cache = cache_temp
                        except Exception as error:
                            # auto remove corrupted files
                            FS.remove(data.cache_file_name)
                    data.calculated = True
                
                # 
                # filepath hashes
                # 
                filepaths_to_watch = watch_filepaths(*args, **kwargs)
                file_hashes = tuple(hash_file(each) for each in filepaths_to_watch)
                
                # 
                # custom_hasher
                # 
                if callable(custom_hasher):
                    hashed_args = custom_hasher(*args, **kwargs)
                    kwargs = None # need to exclude kwargs when custom_hasher is present
                
                # check if this arg combination has been used already
                arg_hash = super_hash((hashed_args, kwargs, depends_on(), file_hashes))
                cache_changed = False
                if arg_hash in data.cache:
                    cached_value, created_at = data.cache[arg_hash]
                    if not is_expired(keep_for_seconds, created_at):
                        return cached_value
                    else:
                        # remove from cache and calculate new value
                        data.cache.pop(arg_hash, None)
                        cache_changed = True
                # if args not in cache, run the function
                result = input_func(*args, **kwargs)
                data.cache[arg_hash] = (time.time(), result)
                cache_changed = True
                if cache_changed:
                    data_to_push = CacheData()
                    data_to_push.calculated      = deepcopy(data.calculated)
                    data_to_push.cache_file_name = deepcopy(data.cache_file_name)
                    data_to_push.deep_hash       = deepcopy(data.deep_hash)
                    data_to_push.cache           = deepcopy(data.cache)
                    worker_que.put(data_to_push, block=False) # use a different process for saving to disk to prevent slowdown
                    return result
            return wrapper
        return real_decorator

def worker():
    global worker_que
    import queue
    import threading
    from threading import Thread
    
    while threading.main_thread().is_alive():
        try:
            if worker_que is not None:
                data = worker_que.get(timeout=0.1) # 0.1 second. Allows for checking if the main thread is alive
                while not worker_que.empty(): # so we only write the latest value
                    data = worker_que.get(block=False)
                FS.clear_a_path_for(data.cache_file_name, overwrite=True)
                with open(data.cache_file_name, 'wb') as cache_file:
                    get_pickle().dump((data.deep_hash, data.cache), cache_file, protocol=4)
                worker_que.task_done()
        except queue.Empty:
            continue


def parse_keep_for_seconds(keep_for):
    if keep_for is None:
        return None
    if not isinstance(keep_for, str):
        raise ValueError("keep_for must be None or a duration string like '10s' or '2d'")
    
    cleaned = keep_for.strip().lower()
    # longest suffixes first so "mo" wins over "m"
    for suffix in sorted(TIME_SUFFIXES_IN_SECONDS.keys(), key=len, reverse=True):
        if cleaned.endswith(suffix):
            number_portion = cleaned[: -len(suffix)]
            try:
                amount = float(number_portion)
            except ValueError:
                raise ValueError(f"keep_for '{keep_for}' must start with a number before the unit (examples: 500m, 10s, 1.5h, 2d, 1mo, 1y)")
            return amount * TIME_SUFFIXES_IN_SECONDS[suffix]
    
    valid_units = ", ".join([
        "m (milliseconds)",
        "s (seconds)",
        "h (hours)",
        "d (days)",
        "mo (months ~30d)",
        "y (years ~365d)",
    ])
    raise ValueError(f"keep_for '{keep_for}' must end with one of: {valid_units}")


def is_expired(expiry_seconds, created_at):
    if expiry_seconds is None:
        return False
    if created_at is None:
        return True
    return (time.time() - created_at) >= expiry_seconds
