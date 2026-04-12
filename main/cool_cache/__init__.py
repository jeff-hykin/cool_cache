# from: https://raw.githubusercontent.com/andrewgazelka/smart-cache/master/smart_cache/__init__.py
# (MIT License on PyPi)
# has been modified to use super_hash and work on python3.8

from os import path
import time
import threading

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

class _CacheEntry:
    # sentinel wrapper so (created_at, value) can never be confused
    # with a user value that happens to be a 2-tuple starting with a float
    __slots__ = ("created_at", "value")
    def __init__(self, created_at, value):
        self.created_at = created_at
        self.value = value

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
    def __init__(self):
        self.calculated = False
        self.cache_file_name = ""
        self.deep_hash = ""
        self.arg_hash_to_value = {}
        self.lock = threading.Lock()

# since we only care about latest
worker_que = None
worker_thread = None


def _compute_arg_hash_inputs(args, kwargs, watch_attributes, custom_hasher):
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

    if callable(custom_hasher):
        hashed_args = custom_hasher(*args, **kwargs)
        kwargs = None  # need to exclude kwargs when custom_hasher is present
    return hashed_args, kwargs


def _unwrap_entry(entry):
    # returns a _CacheEntry, upgrading legacy raw values in-place-compatible form
    if isinstance(entry, _CacheEntry):
        return entry
    return _CacheEntry(time.time(), entry)


def cache(folder=NotGiven, depends_on=lambda:None, watch_attributes=[], watch_filepaths=lambda *args, **kwargs:[], custom_hasher=None, bust=False, keep_for=NotGiven):
    global worker_que, worker_thread
    keep_for_value = settings.default_keep_for if keep_for is NotGiven else keep_for
    keep_for_seconds = parse_keep_for_seconds(keep_for_value)

    if folder is NotGiven:
        folder = settings.default_folder

    # save in ram
    if folder is None:
        def decorator_name(input_func):
            in_memory_cache = {}
            mem_lock = threading.Lock()
            def wrapper(*args, **kwargs):
                hashed_args, kwargs_for_hash = _compute_arg_hash_inputs(args, kwargs, watch_attributes, custom_hasher)

                #
                # filepath hashes
                #
                filepaths_to_watch = watch_filepaths(*args, **kwargs)
                file_hashes = tuple(hash_file(each) for each in filepaths_to_watch)

                # check if this arg combination has been used already
                arg_hash = super_hash((hashed_args, kwargs_for_hash, depends_on(), file_hashes))
                with mem_lock:
                    if arg_hash in in_memory_cache:
                        entry = _unwrap_entry(in_memory_cache[arg_hash])
                        in_memory_cache[arg_hash] = entry
                        if is_expired(keep_for_seconds, entry.created_at):
                            in_memory_cache.pop(arg_hash, None)
                        else:
                            return entry.value
                # if args not in cache, run the function
                result = input_func(*args, **kwargs)
                with mem_lock:
                    in_memory_cache[arg_hash] = _CacheEntry(time.time(), result)
                return result
            return wrapper
        return decorator_name

    # save in cold storage
    else:
        import queue
        if worker_que is None:
            worker_que = queue.Queue(maxsize=settings.worker_que_size)
            worker_thread = threading.Thread(target=worker, daemon=True)
            worker_thread.start()
        def real_decorator(input_func):
            function_cache_manager = PerFuncCache()
            function_id = super_hash(input_func)
            function_cache_manager.cache_file_name = path.join(folder, f'{function_id}.pickle')
            function_cache_manager.deep_hash = function_id
            if bust:
                FS.remove(function_cache_manager.cache_file_name)
            def wrapper(*args, **kwargs):
                # load cached values for this function (once, under lock)
                with function_cache_manager.lock:
                    if not function_cache_manager.calculated:
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

                hashed_args, kwargs_for_hash = _compute_arg_hash_inputs(args, kwargs, watch_attributes, custom_hasher)

                #
                # filepath hashes
                #
                filepaths_to_watch = watch_filepaths(*args, **kwargs)
                file_hashes = tuple(hash_file(each) for each in filepaths_to_watch)

                # check if this arg combination has been used already
                arg_hash = super_hash((hashed_args, kwargs_for_hash, depends_on(), file_hashes))
                with function_cache_manager.lock:
                    arg_hash_to_value = function_cache_manager.arg_hash_to_value
                    if arg_hash in arg_hash_to_value:
                        entry = _unwrap_entry(arg_hash_to_value[arg_hash])
                        arg_hash_to_value[arg_hash] = entry
                        if not is_expired(keep_for_seconds, entry.created_at):
                            return entry.value
                        else:
                            arg_hash_to_value.pop(arg_hash, None)

                # if args not in cache, run the function
                result = input_func(*args, **kwargs)

                with function_cache_manager.lock:
                    function_cache_manager.arg_hash_to_value[arg_hash] = _CacheEntry(time.time(), result)
                    # shallow snapshot under the lock so the worker can
                    # iterate/pickle a stable mapping without racing writers
                    snapshot = dict(function_cache_manager.arg_hash_to_value)
                    cache_file_name = function_cache_manager.cache_file_name
                    deep_hash = function_cache_manager.deep_hash

                data_to_push = PerFuncCache()
                data_to_push.calculated = True
                data_to_push.cache_file_name = cache_file_name
                data_to_push.deep_hash = deep_hash
                data_to_push.arg_hash_to_value = snapshot
                try:
                    worker_que.put(data_to_push, block=False)  # use a different process for saving to disk to prevent slowdown
                except queue.Full:
                    # drop this enqueue; the next successful put will supersede it anyway
                    pass
                return result
            return wrapper
        return real_decorator

def worker():
    global worker_que
    import queue

    while threading.main_thread().is_alive():
        try:
            first = worker_que.get(timeout=0.1)  # 0.1 second. Allows for checking if the main thread is alive
        except queue.Empty:
            continue

        # drain the queue but keep only the latest snapshot PER cache file
        # (so writes for function A don't clobber pending writes for function B)
        pending = {first.cache_file_name: first}
        get_count = 1
        while True:
            try:
                item = worker_que.get(block=False)
            except queue.Empty:
                break
            pending[item.cache_file_name] = item
            get_count += 1

        for item in pending.values():
            try:
                FS.clear_a_path_for(item.cache_file_name, overwrite=True)
                with open(item.cache_file_name, 'wb') as cache_file:
                    get_pickle().dump((item.deep_hash, item.arg_hash_to_value), cache_file, protocol=4)
            except Exception:
                pass
        for _ in range(get_count):
            worker_que.task_done()


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
