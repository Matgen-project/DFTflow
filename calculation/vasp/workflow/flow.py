#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from config import WORKFLOW, CONDOR, PACKAGE_ROOT
from utils.spath import SPath


class WorkflowParser:
    def __init__(self, work_root: SPath, comment=None, source=None,
                 modules=None, workflow=None, prog=None, name=None):
        self.work_root = work_root.absolute()
        if comment is None:
            comment = "#!/bin/bash"
        self.comment = comment
        if prog is None:
            prog = "vasp_std"
        self.prog = prog
        if workflow is None:
            workflow = WORKFLOW
        self.workflow = workflow
        self._py = PACKAGE_ROOT / "vasp.py"
        self.name = name
        if source is None:
            self.source = CONDOR.get('SOURCE', 'FILES')
            if self.source:
                self.source = f"source {self.source}"
        if modules is None:
            self.module = CONDOR.get('MODULE', 'MODULES')
            if self.module:
                self.module = f"module load {self.module}"

    def yield_job(self):
        for job_name, job_paras in self.workflow.items():
            yield job_name, job_paras

    def yhrun_prog(self, node, core):
        return f"yhrun -N {node} -n {core} {CONDOR['VASP']['VASP_DIR']}/{self.prog}"

    def parser(self, job_name, job_paras):
        flow = ''
        #task_dir = self.work_root / job_name
        task_dir =  SPath("./")
        converge_txt = task_dir / "converge.txt"
        flow += f"echo \'[...]start {job_name} task\'\n"
        flow += f"if [ ! -d {job_name} ];then\n"
        flow += f"  mkdir {job_name} && cd {job_name} || exit\n"
        flow += f"else\n"
        flow += f"  cd {job_name}\n"
        flow += f"fi\n"
        node = job_paras.get("node")
        core = job_paras.get("core")
        if node is None:
            node = 1
            core = 24
        if core is None:
            core = 24 * node
        try_num = job_paras.get("try_num")
        if try_num is None:
            try_num = 1
        ignore_txt = task_dir / "ignore.txt"
        flow += f"echo \'[...]prepare {job_name} inputs.\'\n"
        flow += f"python {self._py} generate --work_dir {task_dir}\n"
        flow += f"for ((try_num=1;try_num<={try_num};try_num++))\n"
        flow += "  do\n"
        flow += f"  echo \"[...]task {job_name} round: $try_num on {node} node {core} core\"\n"
        flow += f"  {self.yhrun_prog(node, core)} > yh.log\n"
        flow += f"  if [ $? -eq 0 ]; then\n"
        flow += f"    echo \"[...]calc step: $try_num completed!\"\n"
        flow += f"    echo \"[...]check calculation result...\"\n"
        flow += f"    python {self._py} errors --work_dir {task_dir}\n"
        flow += f"    python {self._py} converge --work_dir {task_dir}\n"
        flow += f"    if [ -f \"{converge_txt}\" ];then\n"
        flow += f"      python {self._py} spin --work_dir {task_dir}\n"
        flow += f"      break\n"
        flow += f"    fi\n"
        flow += f"  else\n"
        flow += f"    echo \'[...]yhrun command failed! check errors\'\n"
        flow += f"    python {self._py} errors --work_dir {task_dir}\n"
        flow += f"  fi\n"
        flow += f"  echo \'[...]calculation not done, prepare to next loop\'\n"
        flow += f"  python {self._py} update --work_dir {task_dir}\n"
        flow += f"done\n"
        flow += f"if [ ! -f \"{converge_txt}\" ];then\n"
        flow += f"  echo \'[...]The job in the specified setting is not completed, " \
                f"       check if it can be ignored\' \n"
        flow += f"  if [ ! -f \"{ignore_txt}\" ];then\n"
        flow += f"    echo \'[...]subsequent calculations are not allowed, job exits...\'\n"
        flow += f"    echo '{job_name}\t failed' >> ../stat.log\n"
        flow += f"    exit\n"
        flow += f"  else\n"
        flow += f"    echo \'[...]errors can be ignored, preparing for the next calculation\'\n"
        flow += f"    python {self._py} spin --work_dir {task_dir}\n"
        flow += f"    echo '{job_name}\t successed' >> ../stat.log\n"
        flow += f"  fi\n"
        flow += f"else\n"
        flow += f"  echo \'[...]{job_name} job done!\'\n"
        flow += f"  python {self._py} spin --work_dir {task_dir}\n"
        flow += f"  echo '{job_name}\t successed' >> ../stat.log\n"
        flow += f"fi\n"
        flow += f"cd ..\n"

        return flow

    def _get(self):
        b = ''
        b += f"{self.comment}\n"
        b += f"{self.source}\n"
        b += f"{self.module}\n"
        b += f"echo \'[...]TASK START!\'\n"
        for step, paras in self.yield_job():
            b += self.parser(step, paras)
        b += f"python {self._py} summary --root {self.work_root}\n"
        b += f"echo \'[...]TASK DONE!\'"
        return b

    def write_sh(self):
        filename = self.work_root.name + ".sh"
        sh_path = self.work_root / filename
        sh_path.write_text(self._get())
        return self.work_root, filename


if __name__ == '__main__':
    pass
