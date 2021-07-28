#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from utils.spath import SPath
from utils.tools import smart_fmt

from pymatgen.io.vasp.outputs import Outcar


class OUTCAR:
    def __init__(self, outcar: SPath):
        self.outcar = outcar

    def converged(self):
        for line in self.outcar.readline_text_reversed():
            if "reached required accuracy - stopping structural energy minimisation" in line:
                return True

        return False

    def finished(self):
        for line in self.outcar.readline_text_reversed():
            if "General timing and accounting informations for this job" in line:
                return True

        return False

    @property
    def data(self):
        return Outcar(str(self.outcar))


if __name__ == '__main__':
    pass
