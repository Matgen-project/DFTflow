#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pandas
import logging

from utils.tools import dataframe_from_dict
from utils.spath import SPath


class LogCsv:
    def __init__(self, csv: SPath):
        self._path = csv
        self._read()

    def __repr__(self):
        return str(self._path)

    def _read(self):
        self._csv = None
        if self._path.exists():
            self._csv = pandas.read_csv(self._path, sep="\t")

    @property
    def csv(self):
        self._read()
        return self._csv

    @csv.setter
    def csv(self, new_csv):
        self._csv = new_csv

    @property
    def path(self):
        return self._path

    def __str__(self):
        return repr(self.csv)

    def apply_(self, df: pandas.DataFrame):
        return df.to_csv(self._path, sep="\t", na_rep="?", index=False)

    def apply(self):
        self.apply_(self.csv)

    def add(self, new_data):
        tmp = self.csv.copy()
        tmp = tmp.append(new_data, ignore_index=True)
        self.csv = tmp
        return tmp

    def alter(self, lb, old_val, new_val):
        tmp = self.csv.copy()
        tmp = self._alter(tmp, lb, old_val, new_val)
        self.csv = tmp
        return tmp

    def alter_(self, match_lb, match_val, alter_lb, alter_val):
        tmp = self.csv.copy()
        tmp = self.__alter(tmp, match_lb, match_val, alter_lb, alter_val)
        self.csv = tmp
        return tmp

    @staticmethod
    def _alter(df, mk, mv, nv):
        df.loc[df[mk] == mv, mk] = nv
        return df

    @staticmethod
    def __alter(df, mk, mv, ak, av):
        df.loc[df[mk] == mv, ak] = av
        return df

    def alter_many(self, match_lb, match_val, values):
        tmp = self.csv.copy()
        for k, v in values.items():
            tmp = self.__alter(tmp, match_lb, match_val, k, v)
        self.csv = tmp
        return tmp

    def drop_one(self, label, value, **kwargs):
        tmp = self.csv.copy()
        row_list = tmp.loc[tmp[label] == value].index.tolist()
        tmp = tmp.drop(row_list, inplace=True, **kwargs)
        self.csv = tmp
        return tmp

    def contain(self, label, val):
        tmp = self.csv.copy()
        return bool(tmp.loc[tmp[label] == val].index.tolist())

    def get(self, label, val):
        tmp = self.csv.copy()
        return tmp.loc[tmp[label] == val]

    def touch(self, head: list, values: list):
        nov = len(values)
        tmp = dataframe_from_dict(
            dict(zip(head, values[0]))
        )
        for idx in range(1, nov):
            tmp = tmp.append(
                dataframe_from_dict(
                    dict(zip(head, values[idx]))), ignore_index=True
            )
        self.apply_(tmp)


class Notice:
    pass


if __name__ == '__main__':
    pass
