#!/usr/bin/env python3
# -*- coding: utf-8 -*-


from enum import Enum
import re

import seekpath
import numpy as np
from utils.spath import SPath
from utils.tools import smart_fmt
from calculation.vasp.inputs import POSCAR


class KPOINTSModes(Enum):
    Gamma = 1
    Monkhorst = 2
    LineMode = 3

    def __str__(self):
        return self.name

    @staticmethod
    def from_string(s):
        c = s.lower()[0]
        for m in KPOINTSModes:
            if m.name.lower()[0] == c:
                return m
        return None


class KPOINTS:
    mode = KPOINTSModes

    def __init__(self, title="MATGEN KPT", scheme=0, interval_of_kpoints=40, coord_type=None,
                 style=mode.Monkhorst, kmesh=(1, 1, 1), shift=(0, 0, 0), kpath=None, labels=None):
        self.title = title
        self.scheme = scheme
        self._interval_of_k = interval_of_kpoints
        self._style = style
        self.kmesh = kmesh
        self.shift = shift
        self.kpath = kpath
        self.labels = labels
        self.coord_type = coord_type

    @property
    def style(self):
        return self._style

    @style.setter
    def style(self, style):
        if isinstance(style, str):
            style = KPOINTSModes.supported_modes.from_string(style)
        self._style = style

    @property
    def nkpt(self):
        return self._interval_of_k

    @nkpt.setter
    def nkpt(self, new_val):
        self._interval_of_k = new_val

    @classmethod
    def from_file(cls, filepath: SPath, **kwargs):
        file = filepath.readline_text(**kwargs)
        title = next(file)
        num_kpt = smart_fmt(next(file))
        style = next(file).lower()

        if style[0] in ["g", "m"]:
            style = KPOINTS.mode.from_string(style)
            kmesh = [smart_fmt(i) for i in next(file).split()]
            shift = [smart_fmt(j) for j in next(file).split()]
            return cls(title=title, style=style, kmesh=kmesh, shift=shift, scheme=num_kpt)
        if style[0] == "l":
            style = KPOINTS.mode.LineMode
            coord_type = next(file)
            kpath = []
            labels = []
            patt = re.compile(r'([e0-9.\-]+)\s+([e0-9.\-]+)\s+([e0-9.\-]+)'
                              r'\s*!*\s*(.*)')
            while True:
                try:
                    line = next(file)
                except StopIteration:
                    break
                else:
                    m = patt.match(line)
                    if m:
                        kpath.append([smart_fmt(m.group(1)), smart_fmt(m.group(2)),
                                      smart_fmt(m.group(3))])
                        labels.append(m.group(4).strip())
            return cls(style=style, kpath=kpath, labels=labels,
                       interval_of_kpoints=num_kpt, coord_type=coord_type)

    def get_kmesh(self, poscar: POSCAR, mesh=0.02):
        va, vb, vc = poscar.lattice.reciprocal_lattice().get_latt_len()
        if mesh == 0:
            self.style = KPOINTS.mode.Gamma
            self.kmesh = [1, 1, 1]
        ratio = list(
            map(lambda x: int(
                np.floor(round(x / (2 * np.pi * mesh)))),
                [va, vb, vc])
        )
        for idx, v in enumerate(ratio):
            if v == 0:
                ratio[idx] = 1
        self.kmesh = ratio

    def get_hk_path(self, poscar: POSCAR, **kwargs):
        hk_path = seekpath.get_path(
            poscar.structure, **kwargs
        )
        pc = hk_path.get("point_coords")
        pl = hk_path.get("path")

        coords, lbs = [], []
        for item in pl:
            for plb in item:
                coords.append(
                    pc.get(plb)
                )
                lbs.append(plb)
        coords = np.asarray(coords)
        lbs = np.asarray(lbs)
        self.kpath = coords
        self.labels = lbs

    def write(self, kpoints: SPath):
        if kpoints.exists():
            if not kpoints.is_empty():
                kpoints.copy_to(des=kpoints.parent / "KPOINTS_step_0", mv_org=True)
        kpoints.write_text(str(self))

    def __str__(self):
        string = ''
        string += f"{self.title}\n"
        if self.style in [KPOINTSModes.Gamma, KPOINTSModes.Monkhorst]:
            string += f"{self.scheme}\n"
            string += f"{self.style}\n"
            kmesh_string = '\t'.join([str(i) for i in self.kmesh])
            shift_string = '\t'.join([str(i) for i in self.shift])
            string += f"{kmesh_string}\n"
            string += f"{shift_string}"
        else:
            string += f"{self.nkpt}\n"
            string += f"{self.style}\n"
            string += "Rec\n"
            for idx, p in enumerate(self.kpath):
                kps = '\t'.join([str(i) for i in p]) + '\t! ' + self.labels[idx] + '\n'
                string += kps

        return string


if __name__ == '__main__':
    pass
