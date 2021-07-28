#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from subprocess import getstatusoutput
from time import sleep
import pandas
from multiprocessing.pool import Pool


def retry(max_retry=None, inter_time=None):
    if max_retry is None:
        max_retry = 3
    if inter_time is None:
        inter_time = 2

    def decorator(func):
        def inner(*args, **kwargs):
            exit_code, results = func(*args, **kwargs)
            number = 0
            if exit_code != 0:
                while number < max_retry:
                    sleep(inter_time)
                    number += 1
                    print(f'{number} times')
                    exit_code, results = func(*args, **kwargs)
                    if exit_code == 0:
                        break
            return exit_code, results

        return inner

    return decorator


def dataframe_from_dict(data: dict):
    tmp = {}
    for k, v in data.items():
        tmp[k] = [v]
    new_data = pandas.DataFrame.from_dict(tmp)
    del tmp
    return new_data


def get_output(unix_cmd):
    return getstatusoutput(unix_cmd)


def smart_fmt(inputs):
    if isinstance(inputs, str):
        if inputs.isalpha():
            return inputs
        else:
            if '.' in inputs or 'e' in inputs or 'E' in inputs:
                return float(inputs)
            return int(inputs)
    if isinstance(inputs, list) or isinstance(inputs, tuple):
        return [smart_fmt(i) for i in inputs]

    raise TypeError


def multi_run(generator, func, n, *args, **kwargs):
    pool = Pool(n)
    results = []
    for item in generator:
        results.append(
            pool.apply_async(func, args=(item,), *args, **kwargs)
        )

    pool.close()
    pool.join()
    for r in results:
        try:
            yield r.get()
        except:
            continue


if __name__ == '__main__':
    pass
