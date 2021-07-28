#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re

from utils.spath import SPath
from utils.tools import smart_fmt


class INCAR:
    LIST_TYPE_KEYS = ("LDAUU", "LDAUL", "LDAUJ", "MAGMOM", "DIPOL",
                      "LANGEVIN_GAMMA", "QUAD_EFG", "EINT")
    BOOLEAN_TYPE_KEYS = ("LDAU", "LWAVE", "LSCALU", "LCHARG", "LPLANE", "LUSE_VDW",
                         "LHFCALC", "ADDGRID", "LSORBIT", "LNONCOLLINEAR")
    FLOAT_TYPE_KEYS = ("EDIFF", "SIGMA", "TIME", "ENCUTFOCK", "HFSCREEN",
                       "POTIM", "EDIFFG", "AGGAC", "PARAM1", "PARAM2")
    INT_TYPE_KEYS = ("NSW", "NBANDS", "NELMIN", "ISIF", "IBRION", "ISPIN",
                     "ICHARG", "NELM", "ISMEAR", "NPAR", "LDAUPRINT", "LMAXMIX",
                     "ENCUT", "NSIM", "NKRED", "NUPDOWN", "ISPIND", "LDAUTYPE",
                     "IVDW")

    def __init__(self, **kwargs):
        self._paras = kwargs

    @classmethod
    def from_file(cls, filepath: SPath, **kwargs):
        regex = re.compile(r"(\w+)\s*=\s*(.*)")
        paras = {}
        for line in filepath.readline_text(**kwargs):
            if ';' in line:
                for child_line in line.split(';'):
                    key, val = regex.findall(child_line)[0]
                    paras[key] = cls._clear_paras(key, val)
            else:
                key, val = regex.findall(line)[0]
                paras[key] = cls._clear_paras(key, val)
        return cls(**paras)

    @staticmethod
    def _clear_paras(key, raw_val):
        if key in INCAR.LIST_TYPE_KEYS:
            val = []
            regex = re.compile(r"\s+")
            for item in regex.split(raw_val):
                val.append(smart_fmt(item))

            return val

        elif key in INCAR.BOOLEAN_TYPE_KEYS:
            r = re.match(r"^\.?([T|F|t|f])[A-Za-z]*\.?", raw_val)
            if r:
                if 't' in r.group(1).lower():
                    return True
                else:
                    return False

        elif key in INCAR.FLOAT_TYPE_KEYS or key in INCAR.INT_TYPE_KEYS:
            return smart_fmt(raw_val)
        else:
            return raw_val

    @property
    def paras(self):
        return self._paras

    def __setitem__(self, key, value):
        self._paras[key.strip()] = self._clear_paras(key.strip(), str(value))

    def __getitem__(self, item):
        return self._paras.get(item)

    @staticmethod
    def _make_string(key, val):
        if key in INCAR.LIST_TYPE_KEYS:
            return ' '.join([str(i) for i in val])
        elif key in INCAR.INT_TYPE_KEYS or key in INCAR.FLOAT_TYPE_KEYS:
            return str(val)
        elif key in INCAR.BOOLEAN_TYPE_KEYS:
            return val
        else:
            if not isinstance(val, str):
                val = str(val)
            return val

    def write(self, incar: SPath):
        if incar.exists():
            if not incar.is_empty():
                incar.copy_to(des=incar.parent / "INCAR_step_0", mv_org=True)
        for key, val in self.paras.items():
            incar.add_to_text(
                f"{key} = {self._make_string(key, val)}"
            )

    def __str__(self):
        return repr(self.paras)

    def get(self, item):
        return self.paras.get(item)


if __name__ == '__main__':
    pass
