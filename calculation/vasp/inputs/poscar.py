#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
from collections import OrderedDict

import spglib as spg

from config import HUBBARD_U
from utils.spath import SPath
from utils.tools import smart_fmt

ELEMENTS = {
    1: "H",
    2: "He",
    3: "Li",
    4: "Be",
    5: "B",
    6: "C",
    7: "N",
    8: "O",
    9: "F",
    10: "Ne",
    11: "Na",
    12: "Mg",
    13: "Al",
    14: "Si",
    15: "P",
    16: "S",
    17: "Cl",
    18: "Ar",
    19: "K",
    20: "Ca",
    21: "Sc",
    22: "Ti",
    23: "v",
    24: "Cr",
    25: "Mn",
    26: "Fe",
    27: "Co",
    28: "Ni",
    29: "Cu",
    30: "Zn",
    31: "Ga",
    32: "Ge",
    33: "As",
    34: "Se",
    35: "Br",
    36: "Kr",
    37: "Rb",
    38: "Sr",
    39: "Y",
    40: "Zr",
    41: "Nb",
    42: "Mo",
    43: "Tc",
    44: "Ru",
    45: "Rh",
    46: "Pd",
    47: "Ag",
    48: "Cd",
    49: "In",
    50: "Sn",
    51: "Sb",
    52: "Te",
    53: "I",
    54: "Xe",
    55: "Cs",
    56: "Ba",
    57: "La",
    58: "Ce",
    59: "Pr",
    60: "Nd",
    61: "Pm",
    62: "Sm",
    63: "Eu",
    64: "Gd",
    65: "Tb",
    66: "Dy",
    67: "Ho",
    68: "Er",
    69: "Tm",
    70: "Yb",
    71: "Lu",
    72: "Hf",
    73: "Ta",
    74: "W",
    75: "Re",
    76: "Os",
    77: "Ir",
    78: "Pt",
    79: "Au",
    80: "Hg",
    81: "Tl",
    82: "Pb",
    83: "Bi",
    84: "Po",
    85: "At",
    86: "Rn",
    87: "Fr",
    88: "Ra",
    89: "Ac",
    90: "Th",
    91: "Pa",
    92: "U",
    93: "Np",
    94: "Pu",
    95: "Am",
    96: "Cm",
    97: "Bk",
    98: "Cf",
    99: "Es",
    100: "Fm",
    101: "Md",
    102: "No",
    103: "Lr",
    104: "Rf",
    105: "Db",
    106: "Sg",
    107: "Bh",
    108: "Hs",
    109: "Mt",
    110: "Ds",
    111: "Rg",
    112: "Cn",
    113: "Uut",
    114: "Uuq",
    115: "Uup",
    116: "Uuh",
    117: "Uus",
    118: "Uuo"
}


class _Lattice:
    def __init__(self, latt, scale=None):
        self._latt = np.around(
            np.asarray(latt).reshape((3, 3)), decimals=6
        )
        if scale is not None:
            self._latt *= scale

    def get_latt_len(self):
        return [np.linalg.norm(x) for x in self._latt]

    @property
    def a(self):
        return self.get_latt_len()[0]

    @property
    def b(self):
        return self.get_latt_len()[1]

    @property
    def c(self):
        return self.get_latt_len()[2]

    @property
    def lattice(self):
        return self._latt

    @property
    def inv_lattice(self):
        return np.linalg.inv(self._latt)

    def get_cart_coords(self, frac_coords):
        return np.dot(np.array(frac_coords), self._latt)

    def get_frac_coords(self, cart_coords):
        return np.dot(np.array(cart_coords), self.inv_lattice())

    def reciprocal_lattice(self):
        return _Lattice(2 * np.pi * np.linalg.inv(self._latt).T)

    def reciprocal_lattice_crystallographic(self):
        return _Lattice(self.reciprocal_lattice().lattice / (2 * np.pi))


class POSCAR:
    def __init__(self, title='', scale=None, lattice=None,
                 symbol=None, symbol_num=None, coords=None, is_cart=True):
        self.title = title
        self.scale = scale
        self.lattice = _Lattice(lattice, scale)
        self.symbol = symbol
        self.symbol_num = symbol_num
        self.coords = coords
        self.is_cart = is_cart
        self.coord_type = "Direct" if not is_cart else "Cartesian"

    @classmethod
    def from_file(cls, filepath: SPath, **kwargs):
        file = filepath.readline_text(**kwargs)
        title = next(file)
        scale = smart_fmt(next(file))
        latt = []
        for _ in range(3):
            latt.append(
                np.asarray(
                    next(file).split(), dtype=float
                )
            )
        latt = np.asarray(latt)
        symbol = next(file).split()
        nums = [smart_fmt(i) for i in next(file).split()]
        nt = np.asarray(nums, dtype=int).sum()
        coord_type = next(file)
        is_cart = False if 'd' == coord_type.lower()[0] else True
        coords = []
        for _ in range(nt):
            coords.append(
                np.asarray(
                    next(file).split()[:3], dtype=float
                )
            )
        coords = np.asarray(coords)

        return cls(title, scale, latt, symbol, nums, coords, is_cart)

    @property
    def numbers(self):
        tmp = {v: k for k, v in ELEMENTS.items()}
        numbers = []
        for idx, e in enumerate(self.symbol):
            n = tmp.get(e)
            numbers.extend([n, ] * self.symbol_num[idx])
        del tmp
        return numbers

    @property
    def structure(self):
        return self.lattice.lattice, self.coords, self.numbers

    def get_primitive(self):
        new_latt, new_coords, new_numbers = spg.find_primitive(
            cell=self.structure
        )
        d = OrderedDict()
        for item in [ELEMENTS.get(i) for i in new_numbers]:
            if d.get(item) is None:
                d[item] = 1
            else:
                d[item] += 1
        new_symbol = list(d.keys())
        new_symbol_num = list(d.values())
        title = ''
        for idx, s in enumerate(new_symbol):
            s += str(new_symbol_num[idx])
            title += s

        return POSCAR(title, 1.0, new_latt, new_symbol,
                      new_symbol_num, new_coords, is_cart=False)

    def __repr__(self):
        latt_str = ''
        for i in self.lattice.lattice:
            latt_str += '\t'.join(str(j) for j in i)
            latt_str += '\n'
        coords_str = ''
        for k in self.coords:
            coords_str += '\t'.join(str(m) for m in k)
            coords_str += '\n'
        symbol_str = '\t'.join(self.symbol)
        symbol_num_str = '\t'.join([str(n) for n in self.symbol_num])
        return f"{self.title}\n" \
               f"{self.scale}\n" \
               f"{latt_str}" \
               f"{symbol_str}\n" \
               f"{symbol_num_str}\n" \
               f"{self.coord_type}\n" \
               f"{coords_str}"

    def write(self, filepath: SPath, **kwargs):
        filepath.write_text(str(self), **kwargs)

    def get_hubbard_u_if_need(self):
        uo, uvi = [], []
        huv, huo = HUBBARD_U.get("Uval"), HUBBARD_U.get("Uorbit")
        for e in self.symbol:
            if huv.get(e) is None:
                uo.append(-1)
                uvi.append(0)
            else:
                uo.append(huo.get(e))
                uvi.append(huv.get(e))
        flag = False
        for f in uo:
            if f != -1:
                flag = True
        if not flag:
            return None
        uvj = [0, ] * len(self.symbol)
        lm = 4 if max(uo) == 2 else 6
        u = {
            "LDAU": ".T",
            "LDAUTYPE": 2,
            "LDAUL": " ".join([str(i) for i in uo]),
            "LDAUU": " ".join([str(j) for j in uvi]),
            "LDAUJ": " ".join([str(k) for k in uvj]),
            "LMAXMIX": lm
        }
        return u




if __name__ == '__main__':
    pass
