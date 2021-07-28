#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
from monty import os
import pandas
import pexpect

from utils.spath import SPath
from utils.tools import retry, get_output, dataframe_from_dict
from utils import RUNNING_JOB_LOG, HPC_LOG, TEMP_FILE, YHI_LABEL, YHQ_LABEL


class TianHeTime:
    def __init__(self, days=0, hours=0, mins=0, secs=0):
        if not isinstance(days, int):
            days = int(days)
        if not isinstance(hours, float):
            hours = float(hours)
        if not isinstance(mins, float):
            mins = float(mins)
        if not isinstance(secs, float):
            secs = float(secs)
        if secs > 60:
            mins += secs // 60
            secs %= 60
        if mins > 60:
            hours += mins
            mins %= 60
        if hours > 24:
            days += hours // 24
            hours %= 24

        self.days = days
        self.hours = hours
        self.mins = mins
        self.secs = secs

    def __gt__(self, other):
        return (self.days, self.hours, self.mins, self.secs) \
               > (other.days, other.hours, other.mins, other.secs)

    def __eq__(self, other):
        return (self.days, self.hours, self.mins, self.secs) \
               == (other.days, other.hours, other.mins, other.secs)

    def __repr__(self):
        return f"{self.days}-{self.hours}:{self.mins}:{self.secs}"

    @classmethod
    def from_string(cls, time_string):
        if '-' in time_string:
            days, rems = time_string.split('-')
        else:
            days, rems = 0, time_string
        hms_list = [int(i) for i in rems.split(':')]
        z = [0, ] * 3
        hms_list.reverse()
        for idx, t in enumerate(hms_list):
            z[idx] = t
        z.append(int(days))
        z.reverse()

        return cls(*z)


class TianHeJob:
    def __init__(self, job_id=None, job_path=None, job_stat=None,
                 node=1, core=24, partition="work", name=None):
        self.id = job_id
        self.path = job_path
        self.stat = job_stat
        self.node = node
        self.core = core
        self.partition = partition
        self.name = name

    @retry(max_retry=5, inter_time=5)
    def yhcancel(self):
        ok, _ = get_output(f"yhcancel {self.id}")
        if ok != 0:
            return ok, None
        RUNNING_JOB_LOG.drop_one(label="JOBID", value=self.id)
        return 0, None

    @staticmethod
    def _yhbatch_parser(output, **kwargs):
        job_id = output.split()[-1]
        kwargs.update({"JOBID": job_id})
        return 0, kwargs

    @staticmethod
    def _yhcontrol_parser(output):
        regex = re.compile(r"\s*(.*?)=(.*?)\s+?")
        control = {}
        for keyword in YHQ_LABEL:
            for key, val in regex.findall(output):
                key = key.upper()
                if keyword == key:
                    control.update({key: int(val) if val.isnumeric() else val})
                else:
                    if "NumNodes".upper() == key:
                        control.update({"NODE": int(val)})
                    if "Account".upper() == key:
                        control.update({"USER": val})
                    if "NodeList".upper() == key:
                        control.update({"NODELIST(REASON)": val})
                    if "RunTime".upper() == key:
                        control.update({"TIME": val})
                    if "JobState".upper() == key:
                        control.update({"ST": val})
        return 0, control

    @retry(max_retry=5, inter_time=5)
    def yhbatch(self):
        with os.cd(self.path):
            ok, output = get_output(f"yhbatch -p {self.partition} "
                                    f"-N {self.node} -n {self.core} {self.name}")
        if ok != 0:
            return ok, None
        return self._yhbatch_parser(output, **{"WORKDIR": self.path,
                                               "NAME": self.name})

    @retry(max_retry=5, inter_time=5)
    def yhrun(self):
        pass

    @retry(max_retry=5, inter_time=5)
    def yhcontrol_show_job(self):
        ok, output = get_output(f"yhcontrol show job {self.id}")
        if ok != 0:
            return ok, None
        _, update_data = self._yhcontrol_parser(output)
        job_id = update_data["JOBID"]
        try:
            if not RUNNING_JOB_LOG.contain("JOBID", job_id):
                RUNNING_JOB_LOG.add(update_data)
            else:
                RUNNING_JOB_LOG.alter_many("JOBID", job_id, update_data)
        except:
            return 1, None
        else:
            RUNNING_JOB_LOG.apply()
            return 0, update_data

    def get_time(self, **kwargs):
        if RUNNING_JOB_LOG.contain("JOBID", self.id):
            job = RUNNING_JOB_LOG.get("JOBID", self.id)
            job_cn = job["TIME"]
            return TianHeTime.from_string(job_cn.values.item())
        TianHeWorker(**kwargs).flush()
        if not RUNNING_JOB_LOG.contain("JOBID", self.id):
            return None
        return self.get_time()

    def exceeds_time(self, limit_time=TianHeTime(3, 0, 0, 0), **kwargs):
        if not isinstance(limit_time, TianHeTime):
            try:
                if isinstance(limit_time, str):
                    limit_time = TianHeTime.from_string(limit_time)
                elif isinstance(limit_time, list) or isinstance(limit_time, tuple):
                    limit_time = TianHeTime(*limit_time)
            except:
                return None
        _time = self.get_time(**kwargs)
        if _time is not None:
            return _time > limit_time
        return None


class TianHeWorker:
    def __init__(self, partition="work", total_allowed_node=50,
                 used_node=0, idle_node=None):
        self.partition = partition
        self.alloc = total_allowed_node
        self._used = used_node
        self._idle = idle_node

    @property
    def idle_node(self):
        return self._idle

    @idle_node.setter
    def idle_node(self, val):
        self._idle = val

    @property
    def used_node(self):
        return self._used

    @used_node.setter
    def used_node(self, val):
        self._used = val

    @staticmethod
    def _yhi_parser(log: SPath):
        if log.exists():
            if not log.is_empty():
                dat = log.read_text().split()
                for item in dat:
                    if "/" in item:
                        try:
                            node_info = [int(i) for i in item.split("/")]
                        except:
                            break
                        else:
                            node_info.insert(0, "SLURM")
                            return 0, dataframe_from_dict(
                                dict(zip(YHI_LABEL,
                                         node_info))
                            )
        return 1, None

    @staticmethod
    def _yhq_parser(log: SPath):
        if log.exists():
            if not log.is_empty():
                dat = pandas.read_table(log, sep=r"\s+")
                dat["WORKDIR"] = None
                return 0, dat
        return 1, None

    @retry(max_retry=5, inter_time=5)
    def yhq(self):
        ok, x = get_output(f"yhqueue > {TEMP_FILE}")
        if ok != 0:
            return ok, None
        ok, yhq_data = self._yhq_parser(TEMP_FILE)
        TEMP_FILE.rm_file()
        if ok != 0:
            return ok, None
        return 0, yhq_data

    @retry(max_retry=5, inter_time=5)
    def yhi(self):
        ok, x = get_output(f"yhinfo -s | grep {self.partition} > {TEMP_FILE}")
        if ok != 0:
            return ok, None
        ok, yhi_data = self._yhi_parser(TEMP_FILE)
        TEMP_FILE.rm_file()
        if ok != 0:
            return ok, None

        return 0, yhi_data

    def flush(self):
        _, sys_yhi = self.yhi()
        _, user_yhq = self.yhq()
        self._used = user_yhq["NODES"].sum()
        self._idle = sys_yhi["IDLE"].values[0]
        user_yhi = dataframe_from_dict(
            dict(zip(YHI_LABEL,
                     ["USER", self.alloc, self._used, None, None]))
        )
        all_yhi = sys_yhi.append(user_yhi, ignore_index=True)
        RUNNING_JOB_LOG.apply_(user_yhq)
        HPC_LOG.apply_(all_yhi)

    def yield_time_limit_exceed_jobs(self, time_limit=TianHeTime(3, 0, 0, 0)):
        self.flush()
        for job_id in RUNNING_JOB_LOG.csv["JOBID"]:
            job = TianHeJob(job_id=job_id)
            if job.exceeds_time(time_limit):
                yield job


class TianHeNodes:
    def __init__(self, job_id):
        self.job_id = job_id

    @staticmethod
    def _string_parser(cn_string):
        if "[" not in cn_string:
            return [int(cn_string.strip("cn"))]
        tmp = cn_string.strip("[").strip("]")
        _tmp = tmp.split(',')
        used_nodes = []
        for i in _tmp:
            j = i.replace("cn[", "").replace("]", "")
            if '-' in j:
                s, e = j.split('-')
                used_nodes.extend(
                    [k for k in range(int(s), int(e) + 1)]
                )
            else:
                used_nodes.append(j)
        return used_nodes

    def get_nodes(self, **kwargs):
        if RUNNING_JOB_LOG.contain("JOBID", self.job_id):
            job = RUNNING_JOB_LOG.get("JOBID", self.job_id)
            job_cn = job["NODELIST(REASON)"]
            return self._string_parser(job_cn.values.item())
        TianHeWorker(**kwargs).flush()
        if not RUNNING_JOB_LOG.contain("JOBID", self.job_id):
            return None
        return self.get_nodes()

    @staticmethod
    def _kill_zombie_process(node, key_word):
        child = pexpect.spawn("ssh cn%d" % node)
        try:
            q = child.expect(["yes/no", ""], timeout=5)
            if q == 0:
                child.sendline("yes")
        except (pexpect.EOF, pexpect.TIMEOUT):
            child.close()
            return False
        else:
            child.send(
                "for i in `ps aux | grep %s |awk \'{print $2}\'`;do kill -9 $i;done" % key_word
            )
            child.close()
        return True

    def kill_zombie_process_on_nodes(self, key_word="vasp_std"):
        results = []
        for node in self.get_nodes():
            results.append(
                self._kill_zombie_process(node, key_word)
            )

        return all(results)


if __name__ == "__main__":
    pass
