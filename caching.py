import datetime
import functools 
from dns_structs import Answer, Question
from csv import DictReader, DictWriter
from threading import Lock


def synchronized(lock=None):
    def decorator(wrapped):
        @functools.wraps(wrapped)
        def wrapper(*args, **kwargs):
            with lock:
                return wrapped(*args, **kwargs)
        return wrapper
    return decorator


class CacheItem:
    def __init__(self, data, ttl, cached_at=None):
        self.data = data
        self.ttl = ttl

        if cached_at is not None:
            self.cached_at = cached_at
        else:
            self.cached_at = datetime.datetime.now()


class Cache:
    def __init__(self):
        self.cache = dict()
        self.cache_lock = Lock()
        self.add_answer = synchronized(self.cache_lock)(self.add_answer)
        self.find_answers = synchronized(self.cache_lock)(self.find_answers)

    def add_answer(self, answer, cached_at=None):
        key = (answer.name, answer.tp, answer.cl)
        if key not in self.cache.keys():
            self.cache[key] = []
            
        new_item = CacheItem(answer.data, answer.ttl, cached_at)
        for i in range(len(self.cache[key])):
            item = self.cache[key][i]
            if item.data == new_item.data and new_item.cached_at > item.cached_at:
                self.cache[key][i] = new_item
                return
                
        self.cache[key].append(CacheItem(answer.data, answer.ttl, cached_at))

    def find_answers(self, question):
        key = (question.name, question.tp, question.cl)
        if key in self.cache.keys():
            records = self.cache[key]
            alive_records = self._get_alive_records(records)
            result = [Answer(*(key + (record.ttl, record.data)))
                for record in alive_records]

            self.cache[key] = alive_records
            return result
        return []

    def _get_alive_records(self, records):
        alive_records = []

        for record in records:
            expires_at = record.cached_at + datetime.timedelta(seconds=record.ttl)
            if datetime.datetime.now() < expires_at:
                alive_records.append(record)
        return alive_records


class CsvCacheManager:
    FIELDS = ['name', 'tp', 'cl', 'ttl', 'data', 'cached_at']

    @staticmethod
    def load_cache_from(file_name):
        cache = Cache()

        with open(file_name, 'r', encoding='utf-8') as csv_cache:
            reader = DictReader(csv_cache, CsvCacheManager.FIELDS)
            next(reader)
            for row in reader:
                cached_at = datetime.datetime.strptime(row['cached_at'], '%Y-%m-%d %H:%M:%S.%f')
                cache.add_answer(
                    Answer(row['name'], int(row['tp']), int(row['cl']), 
                        int(row['ttl']), row['data']), cached_at)

        return cache

    @staticmethod
    def save_cache_to(cache, file_name):
        with open(file_name, 'w', encoding='utf-8') as csv_cache:
            with cache.cache_lock:
                writer = DictWriter(csv_cache, CsvCacheManager.FIELDS)
                writer.writeheader()

                for name, tp, cl in cache.cache.keys():
                    for item in cache.cache[(name, tp, cl)]:
                        writer.writerow(
                            {
                                'name': name, 'tp': tp, 'cl': cl, 
                                **item.__dict__
                            })


def cache_test_found():
    record1 = Answer('google.com.', 1, 1, 3, 'data1')
    record2 = Answer('google.com.', 1, 1, 4, 'data2')
    cache = Cache()
    cache.add_answer(record1)
    cache.add_answer(record2)
    for answer in cache.find_answers(Question('google.com.', 1, 1)):
        print(answer.__dict__)


def cache_test_expired():
    record = Answer('google.com.', 1, 1, -1, 'data')
    cache = Cache()
    cache.add_answer(record)
    print(cache.find_answers(Question('google.com.', 1, 1)))


def cache_save_test():
    record1 = Answer('google.com.', 1, 1, 3, 'data1')
    record2 = Answer('google.com.', 1, 1, 4, 'data2')
    cache = Cache()
    cache.add_answer(record1)
    cache.add_answer(record2)

    CsvCacheManager.save_cache_to(cache, 'cache.txt')

def cache_load_test():
    cache = CsvCacheManager.load_cache_from('cache.txt')
    print(cache.cache)
    for answer in cache.find_answers(Question('google.com.', 1, 1)):
        print(answer.__dict__)

if __name__ == "__main__":
    cache_test_found()
    cache_test_expired()
    #cache_save_test()
    #cache_load_test()