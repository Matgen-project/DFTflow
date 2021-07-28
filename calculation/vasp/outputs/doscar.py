#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.spath import SPath
from utils.tools import smart_fmt


class DOSCAR:
    def __init__(self, doscar: SPath):
        self.doscar = doscar

    def read(self):
        doscar = self.doscar.readline_text()
        natoms, *_ = smart_fmt(next(doscar).split())
        for _ in range(4):
            next(doscar)
        ndos = smart_fmt(next(doscar).split()[2])


if __name__ == '__main__':
    pass
