"""
Stub joblib module that falls back to pickle for serialization.
This allows code and tests to import joblib.load and joblib.dump
without requiring the real joblib package.
"""
import pickle

def dump(obj, filename):
    """Serialize object to the given filename using pickle."""
    with open(filename, 'wb') as f:
        pickle.dump(obj, f)

def load(filename):
    """Deserialize object from the given filename using pickle."""
    with open(filename, 'rb') as f:
        return pickle.load(f)
 
class Parallel:
    """Simple sequential parallel execution stub for joblib.Parallel."""
    def __init__(self, n_jobs=None):
        self.n_jobs = n_jobs
    def __call__(self, iterable):
        # Execute tasks sequentially
        return list(iterable)

def delayed(func):
    """Decorator stub for joblib.delayed to wrap functions for parallel execution."""
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper