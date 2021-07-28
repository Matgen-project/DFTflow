#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from utils.spath import SPath


class EIGENVAL:
    def __init__(self, eigenval: SPath):
        self.eigenval = eigenval

    def read(self):
        for line in self.eigenval.readline_text():
            pass


if __name__ == '__main__':
    pass
