#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
from collections import OrderedDict
from calculation.vasp.outputs import OUTCAR, OSZICAR
from calculation.vasp.inputs import INCAR, KPOINTS, POSCAR, POTCAR, KPOINTSModes
from calculation.vasp.workflow import ErrType
from config import WORKFLOW, CONDOR, INCAR_TEMPLATE
from utils.spath import SPath
from utils import ALL_JOB_LOG
from utils.tools import smart_fmt


class VaspRunningJob:
    def __init__(self, calc_dir: SPath):
        self.calc_dir = calc_dir.absolute()
        self._name = self.calc_dir.parent.name
        self._poscar = self.calc_dir / "POSCAR"
        self._contcar = self.calc_dir / "CONTCAR"
        self._incar = self.calc_dir / "INCAR"
        self._kpoints = self.calc_dir / "KPOINTS"
        self._outcar = self.calc_dir / "OUTCAR"
        self._oszicar = self.calc_dir / "OSZICAR"
        self._incar = self.calc_dir / "INCAR"
        self._potcar = self.calc_dir / "POTCAR"
        self._running = self.calc_dir / "running"
        self._jtype = self.calc_dir.name
        self._spin = self.calc_dir / "is_spin.txt"
        self._converge = self.calc_dir / "converge.txt"
        self._ignore = self.calc_dir / "ignore.txt"

    def is_spin(self):
        final_mag = OSZICAR(self._oszicar).final_mag
        if final_mag is not None:
            if abs(final_mag) > 0.004:
                self._spin.write_text(str(final_mag))
                return True
        return False

    def is_converge(self):
        result = OUTCAR(self._outcar)
        if result.finished():
            if result.converged() or INCAR.from_file(self._incar).get("ISIF") != 3:
                self._converge.touch()
                return True
        if not self._ignore.exists():
            ie = self.job_detail.get("ignore_error")
            if ie is not None and ie.lower()[0] == 't':
                self._ignore.touch()
        return False

    def is_finish(self):
        return OUTCAR(self._outcar).finished()

    @property
    def job_id(self):
        _id = self.get_job_id_from_log()
        if _id is not None:
            return _id
        job_ids = self.get_job_ids_from_slurm_file()
        if job_ids:
            return max(job_ids)
        raise FileNotFoundError("Slurm log not found!")

    def get_job_ids_from_slurm_file(self):
        slurm_ids = []
        regex = re.compile(r"\d+")
        for file in self.calc_dir.parent.rglob("slurm*.out"):
            slurm_ids.extend(
                regex.findall(file.name)
            )
        return [int(i) for i in slurm_ids]

    def get_job_id_from_log(self):
        if ALL_JOB_LOG.contain("WORKDIR", self.calc_dir):
            return ALL_JOB_LOG.get("WORKDIR", self.calc_dir)["JOBID"]
        return None

    def automatic_check_errors(self):
        e = ErrType(job_id=self.job_id, running_dir=self.calc_dir)
        e.automatic_error_correction()

    def get_errors(self, error_log):
        e = ErrType(job_id=self.job_id, running_dir=self.calc_dir)
        errors = set(list(e.get_error_from(self.calc_dir / error_log)))
        if not errors:
            print(f"[...]error not found from {error_log}")
        for item, _ in errors:
            print(f"[...]error type: {item.value}")
        return errors

    @property
    def parent_jtype(self):
        return self.job_detail.get("parent")

    @property
    def parent_legacy(self):
        if self.parent_jtype is not None:
            parent_files = self.job_detail.get("parent_files")
            return [] if parent_files is None else parent_files
        return []

    @property
    def job_detail(self):
        return WORKFLOW[self._jtype]

    @property
    def ktype(self):
        ktype = self.job_detail.get("ktype")
        return KPOINTSModes.from_string(ktype)

    @staticmethod
    def _make_comp(val: list, length):
        n = len(val)
        if n < length:
            val.extend([val[-1], ] * (length - n))
        else:
            val = val[:length]
        return val

    @property
    def kpara(self):
        kval = self.job_detail.get("kval")
        return self._make_comp(kval, self.try_)

    @property
    def incar_(self):
        incar_ = self.job_detail.get("incar_paras")
        if incar_ is None:
            return []
        return self._make_comp(incar_, self.try_)

    @property
    def try_(self):
        tyn = self.job_detail.get("try_num")
        return tyn if tyn is not None else 2

    def _inherit_from_parent(self):
        if self.parent_jtype is not None:
            parent_path = self.calc_dir.parent / self.parent_jtype
            if self.parent_legacy:
                for _file in self.parent_legacy:
                    file = parent_path / _file
                    if _file == "CONTCAR":
                        file.copy_to(self.calc_dir / "POSCAR")
                    else:
                        file.copy_to(self.calc_dir)
            parent_is_spin = parent_path / "is_spin.txt"
            if parent_is_spin.exists():
                parent_is_spin.copy_to(self.calc_dir)

        return

    def _get_idx(self):
        if not self._running.exists():
            return 0
        idx = smart_fmt(self._running.read_text())
        if idx >= self.try_:
            return None
        self._running.write_text(data=f"{idx + 1}")
        return idx

    def _write_kpt(self, stru, kval_):
        if self.ktype == KPOINTSModes.LineMode:
            kpoints = KPOINTS(interval_of_kpoints=kval_, style=self.ktype)
            kpoints.get_hk_path(stru)
        else:
            kpoints = KPOINTS(style=self.ktype)
            kpoints.get_kmesh(stru, kval_)
        kpoints.write(self._kpoints)

    def get_inputs_file(self):
        self._inherit_from_parent()
        incar_paras = INCAR_TEMPLATE.get(self._jtype)
        assert incar_paras is not None
        incar = INCAR(**incar_paras)
        if not self._spin.exists() and self.parent_jtype is not None:
            incar["ISPIN"] = 1
        if not self._poscar.exists() and self.parent_jtype is None:
            for tmp in self.calc_dir.parent.walk(pattern=f"*.*"):
                if self._name in tmp.name and tmp.suffix != ".sh":
                    tmp.copy_to(self.calc_dir / "POSCAR")
                    break
        assert self._poscar.exists()
        stru = POSCAR.from_file(self._poscar)
        dft_u = CONDOR.get("METHOD", "DFT_U")
        if dft_u:
            if dft_u.lower()[0] == "t":
                hubbard_u = stru.get_hubbard_u_if_need()
                if hubbard_u is not None:
                    for lb, v in hubbard_u.items():
                        incar[lb] = v
        incar.write(self._incar)

        if not self._potcar.exists():
            potcar_lib = CONDOR.get("VASP", "PSEUDO_POTENTIAL_DIR")
            potcar_lib = SPath(potcar_lib)
            if not potcar_lib.exists():
                raise FileNotFoundError("POTCAR Source not found!")
            POTCAR(lib=potcar_lib).cat(stru, self._potcar)

        self._running.write_text(data=f"{1}")
        self._write_kpt(stru, self.kpara[0])

    def update_input_files(self):
        assert all(
            [self._incar.exists(), self._potcar.exists(),
             self._kpoints.exists(), self._poscar.exists(), self._running.exists()]
        ), RuntimeError
        times = self._get_idx()
        if times is not None:
            try:
                self._write_kpt(stru=POSCAR.from_file(self._poscar),
                                kval_=self.kpara[times])
                uip = self.incar_[times]
            except IndexError:
                return
            else:
                incar = INCAR.from_file(self._incar)
                for key, val in uip.items():
                    incar[key] = val
                incar.write(self._incar)
            finally:
                return


class RunningRoot:
    def __init__(self, root: SPath):
        self._root = root.absolute()
        self._stat = self._root / "stat.log"

    def _results(self):
        res = {}
        for _line in self._stat.readline_text():
            task, stat = _line.strip('\n').split()
            if stat.startswith('s'):
                res[task] = True
            else:
                res[task] = False
        return res

    def successed(self):
        cjr = {}
        for jtype, jres in self._results().items():
            cjr[jtype] = jres
        if len(cjr) == len(WORKFLOW) and all(cjr.values()):
            return True
        return False

    def summary(self):
        if self.successed():
            alter_val = "Successed"
        else:
            alter_val = "Failed"
            for lb, val in self._results().items():
                if not val:
                    alter_val += f"{lb},"
        tmp = ALL_JOB_LOG.alter_("WORKDIR", self._root, alter_lb="RESULT", alter_val=alter_val)
        ALL_JOB_LOG.apply_(tmp)

        return alter_val

    def get_crun_workflow(self):
        if not self._stat.exists():
            return WORKFLOW
        pstat = self._results()
        nstat = OrderedDict()
        for jtype, jparas in WORKFLOW.items():
            if pstat.get(jtype):
                continue
            nstat[jtype] = jparas
        return nstat


if __name__ == '__main__':
    pass
