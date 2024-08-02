#!/bin/bash
#SBATCH --array=1-{{ commands|length }}
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null

{% for command in commands %}
if [ $SLURM_ARRAY_TASK_ID -eq {{ loop.index }} ]; then
  mkdir -p {{ command.cwd }}
  pushd {{ command.cwd }}
  srun --output=stdout --error=stderr {{ command.args|to_bash }}
  popd
fi
{% endfor %}