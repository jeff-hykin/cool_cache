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
settings.default_keep_for = None

TIME_SUFFIXES_IN_SECONDS = {
    # ms is milliseconds to keep the shorthand compact
    "ms": 0.001,
    "s": 1,
    "h": 60 * 60,
    "d": 60 * 60 * 24,
    # 30d + 365d approximations are plenty accurate for cache busting
    "mo": 60 * 60 * 24 * 30,
    "y": 60 * 60 * 24 * 365,
}

class PerFuncCache:
    calculated = False
    cache_file_name = ""
    deep_hash = ""
    arg_hash_to_value = {}

# since we only care about latest
worker_que = None

def cache(folder=NotGiven, depends_on=lambda:None, watch_attributes=[], watch_filepaths=lambda *args, **kwargs:[], custom_hasher=None, bust=False, keep_for=NotGiven):
    global worker_que
    keep_for_value = settings.default_keep_for if keep_for is NotGiven else keep_for
    keep_for_seconds = parse_keep_for_seconds(keep_for_value)
    
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
                    # if old format (before keep_for was added), add current time to it
                    if type(in_memory_cache[arg_hash]) != tuple or len(in_memory_cache[arg_hash]) != 2 or type(in_memory_cache[arg_hash][0]) != float:
                        value = in_memory_cache[arg_hash]
                        in_memory_cache[arg_hash] = (time.time(), value)
                        return value
                    created_at, cached_value = in_memory_cache[arg_hash]
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
            function_cache_manager = PerFuncCache()
            function_id = super_hash(input_func)
            function_cache_manager.cache_file_name = f'cache.ignore/{function_id}.pickle'
            if bust:
                FS.remove(function_cache_manager.cache_file_name)
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
                if not function_cache_manager.calculated:
                    function_cache_manager.deep_hash = function_id
                    if path.exists(function_cache_manager.cache_file_name):
                        try:
                            with open(function_cache_manager.cache_file_name, 'rb') as cache_file:
                                func_hash, cache_temp = get_pickle().load(cache_file)
                                if func_hash == function_cache_manager.deep_hash:
                                    function_cache_manager.arg_hash_to_value = cache_temp
                        except Exception as error:
                            # auto remove corrupted files
                            FS.remove(function_cache_manager.cache_file_name)
                    function_cache_manager.calculated = True
                
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
                arg_hash_to_value = function_cache_manager.arg_hash_to_value
                if arg_hash in arg_hash_to_value:
                    # if old format (before keep_for was added), add current time to it
                    if type(arg_hash_to_value[arg_hash]) != tuple or len(arg_hash_to_value[arg_hash]) != 2 or type(arg_hash_to_value[arg_hash][0]) != float:
                        value = arg_hash_to_value[arg_hash]
                        arg_hash_to_value[arg_hash] = (time.time(), value)
                        return value
                    
                    created_at, cached_value = arg_hash_to_value[arg_hash]
                    if not is_expired(keep_for_seconds, created_at):
                        return cached_value
                    else:
                        # remove from cache and calculate new value
                        arg_hash_to_value.pop(arg_hash, None)
                # if args not in cache, run the function
                result = input_func(*args, **kwargs)
                arg_hash_to_value[arg_hash] = (time.time(), result)
                data_to_push = PerFuncCache()
                data_to_push.calculated        = deepcopy(function_cache_manager.calculated)
                data_to_push.cache_file_name   = deepcopy(function_cache_manager.cache_file_name)
                data_to_push.deep_hash         = deepcopy(function_cache_manager.deep_hash)
                data_to_push.arg_hash_to_value = deepcopy(arg_hash_to_value)
                worker_que.put(data_to_push, block=False) # use a different process for saving to disk to prevent slowdown
                return result
            return wrapper
        return real_decorator

def worker():
    global worker_que
    import queue
    import threading
    
    while threading.main_thread().is_alive():
        try:
            if worker_que is not None:
                function_cache_manager = worker_que.get(timeout=0.1) # 0.1 second. Allows for checking if the main thread is alive
                while not worker_que.empty(): # so we only write the latest value
                    function_cache_manager = worker_que.get(block=False)
                FS.clear_a_path_for(function_cache_manager.cache_file_name, overwrite=True)
                with open(function_cache_manager.cache_file_name, 'wb') as cache_file:
                    get_pickle().dump((function_cache_manager.deep_hash, function_cache_manager.arg_hash_to_value), cache_file, protocol=4)
                worker_que.task_done()
        except queue.Empty:
            continue


def parse_keep_for_seconds(keep_for):
    if keep_for is None:
        return None
    if not isinstance(keep_for, str):
        raise ValueError("keep_for must be None or a duration string like '10s' or '2d'")
    
    cleaned = keep_for.strip().lower()
    for suffix in sorted(TIME_SUFFIXES_IN_SECONDS.keys(), key=len, reverse=True):
        if cleaned.endswith(suffix):
            number_portion = cleaned[: -len(suffix)]
            try:
                amount = float(number_portion)
            except ValueError:
                raise ValueError(f"keep_for '{keep_for}' must start with a number before the unit (examples: 500ms, 10s, 1.5h, 2d, 1mo, 1y)")
            return amount * TIME_SUFFIXES_IN_SECONDS[suffix]
    
    valid_units = ", ".join([
        "ms (milliseconds)",
        "s (seconds)",
        "h (hours)",
        "d (days)",
        "mo (months ~30d)",
        "y (years ~365d)",
    ])
    raise ValueError(f"keep_for '{keep_for}' must end with one of: {valid_units}. For example keep_for='200ms', keep_for='30d', or keep_for='2mo'")


def is_expired(expiry_seconds, created_at):
    if expiry_seconds is None:
        return False
    if created_at is None:
        return True
    return (time.time() - created_at) >= expiry_seconds
