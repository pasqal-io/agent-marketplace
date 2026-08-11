#!/bin/bash
#MSUB -r <<EXPERIMENT_NAME>>
#MSUB -n 1
#MSUB -c 1
#MSUB -T <<WALL_TIME_S>>
#MSUB -q v100l
#MSUB -A <<MSUB_PROJECT_CODE>>
#MSUB -o logs/cea_%I.out
#MSUB -e logs/cea_%I.err
#MSUB -m scratch

cd $BRIDGE_MSUB_PWD
pcocc-rs run ccc-quantum -- bash -c "
    export PULSER_MYQLM_LIGHTWEIGHT_SCHEDULE=1 && \
    export MAX_CONNECTION_ATTEMPS_QLM=10 && \
    source ../pulser-env/bin/activate && \
    python3 submit_<<EXPERIMENT_NAME>>.py --backend cea --job-index $CEA_JOB_INDEX --n-shots <<N_SHOTS>> --max-wait-hours 12
"
