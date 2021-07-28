#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import threading
from time import sleep
from multiprocessing.pool import Pool

from utils.yhurm import TianHeWorker, TianHeJob
from utils.spath import SPath
from utils import ALL_JOB_LOG, ALL_JOB_LABEL
from calculation.vasp.workflow import WorkflowParser
from calculation.vasp.job import RunningRoot
from config import WORKFLOW, CONDOR


class Producer(threading.Thread):
    Finished = True

    def __init__(self, queue):
        super(Producer, self).__init__()
        self.queue = queue

    def run(self):
        if not ALL_JOB_LOG.path.exists():
            raise Exception("available job not found!")

        max_needed_node, max_needed_core = 0, 0
        for _, val in WORKFLOW.items():
            if max_needed_node < val["node"]:
                max_needed_node = val["node"]
            if max_needed_core < val["core"]:
                max_needed_core = val["core"]
        if ALL_JOB_LOG.csv is None:
            raise FileNotFoundError("No structure files found!")
             
        for index, job in ALL_JOB_LOG.csv.iterrows():
            dft_job = TianHeJob(job_stat=job["RESULT"], job_path=job["WORKDIR"],
                                partition=CONDOR.get("ALLOW", "PARTITION"),
                                node=max_needed_node, core=max_needed_core, name=job["NAME"])
            self.queue.put(dft_job)
        self.queue.put(self.Finished)


class Submitter(threading.Thread):
    Finished = True

    def __init__(self, queue, stime=0.5, flush_time=60, **kwargs):
        super(Submitter, self).__init__()
        self.queue = queue
        self.worker = TianHeWorker(**kwargs)
        self.stime = stime
        self.ftime = flush_time
        self.worker.flush()

    def run(self):
        allow_node = CONDOR.getint("ALLOW", "TOTAL_NODE")
        print("Start job submission...")
        print(f"User node limit: {allow_node}")
        while True:
            print(f"User total used node: {self.worker.used_node}")
            print(f"System total idle node: {self.worker.idle_node}")
            job = self.queue.get()
            if job is self.Finished:
                break
            while self.worker.idle_node <= 0 or self.worker.used_node >= allow_node:
                print(f"waiting for idle resource...")
                sleep(self.ftime)
                self.worker.flush()
            exit_code, info = job.yhbatch()
            if exit_code == 0:
                info.update({"ST": "SS"})
                self.worker.idle_node -= job.node
                self.worker.used_node += job.node
            else:
                info.update({"ST": "SF"})
            tmp = ALL_JOB_LOG.alter_many("WORKDIR", job.path, info)
            ALL_JOB_LOG.apply_(tmp)
            sleep(self.stime)


class Npc:
    def __init__(self, structures_path: SPath, interval_time=0.5):
        self.structures_path = structures_path
        self.interval_time = interval_time

    @staticmethod
    def _init(name: SPath, *args, **kwargs):
        filename_dir = name.mkdir_filename()
        name.copy_to(filename_dir, mv_org=True)
        return WorkflowParser(work_root=filename_dir, *args, **kwargs).write_sh()

    @staticmethod
    def _cinit(cpath: SPath, *args, **kwargs):
        cworkflow = RunningRoot(cpath).get_crun_workflow()
        if not cworkflow:
            return cpath, None
        return WorkflowParser(work_root=cpath, workflow=cworkflow,
                              *args, **kwargs).write_sh()

    @staticmethod
    def _make_log(job_dirs):
        jobs = []
        for job in job_dirs:
            root, bash_name = job.get()
            if bash_name is not None:
                jobs.append(["", "PD", root, bash_name, ""])
        try:
            ALL_JOB_LOG.touch(ALL_JOB_LABEL, jobs)
        except (AttributeError, IndexError):
            raise Exception("Job initialization failed !, check structure files or match pattern!")
        else:
            print(f"total: {len(jobs)} jobs initialized!")

        return True

    def init_jobs(self, pat, n=4):
        job_pool = Pool(n)
        job_dirs = []
        for structure in self.structures_path.walk(pattern=pat, is_file=True):
            job = job_pool.apply_async(self._init, args=(structure,))
            job_dirs.append(job)

        job_pool.close()
        job_pool.join()

        return self._make_log(job_dirs)

    def cinit_jobs(self, n=4):
        job_pool = Pool(n)
        job_dirs = []
        for structure in self.structures_path.walk(pattern="*", is_file=False):
            job = job_pool.apply_async(self._cinit, args=(structure,))
            job_dirs.append(job)
        job_pool.close()
        job_pool.join()

        return self._make_log(job_dirs)

    def post_process(self):
        pass


if __name__ == '__main__':
    pass
