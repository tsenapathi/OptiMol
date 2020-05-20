"""

Same as slurm master but directly packaged as a python script to be run from one node
Params to be blended/changed :


"""
import os
import sys

script_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(script_dir, '..', '..'))

import argparse
import torch

from utils import Dumper, soft_mkdir
from model import model_from_json

from cbas.slurm.sampler import main as sampler_main
from cbas.slurm.docker import one_node_main as docker_main
from cbas.slurm.trainer import main as trainer_main

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument('--prior_name', type=str, default='inference_default')  # the prior VAE (pretrained)
    parser.add_argument('-n', '--name', type=str, default='search_vae')  # the name of the experiment
    parser.add_argument('--iters', type=int, default=2)  # Number of iterations
    parser.add_argument('--oracle', type=str, default='qed')  # 'qed' or 'docking' or 'qsar'

    # SAMPLER
    parser.add_argument('--max_samples', type=int, default=3000)  # Nbr of samples at each iter

    # DOCKER
    parser.add_argument('--server', type=str, default='pasteur', help='server to run on')  # the prior VAE (pretrained)
    parser.add_argument('--ex', type=int, default=16)  # Nbr of samples at each iter

    # TRAINER
    parser.add_argument('--quantile', type=float, default=0.6)  # quantile of scores accepted
    parser.add_argument('--uncertainty', type=str, default='gaussian')  # the mode of the oracle

    # GENTRAIN
    parser.add_argument('--procs', type=int, default=10)  # Number of processes for VAE dataloading
    parser.add_argument('--epochs', type=int, default=1)  # Number of iterations
    parser.add_argument('--learning_rate', type=float, default=1e-4)  # Number of iterations
    parser.add_argument('--beta', type=float, default=0.2)  # KL weight in loss function
    parser.add_argument('--clip_grad_norm', type=float, default=5.0)  # quantile of scores accepted
    parser.add_argument('--opti', type=str, default='adam')  # the mode of the oracle
    parser.add_argument('--sched', type=str, default='elr')  # the mode of the oracle

    # =======

    args, _ = parser.parse_known_args()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    assert args.oracle in ['qed', 'docking', 'qsar']


    def setup():
        pass
        soft_mkdir(os.path.join(script_dir, 'results'))
        soft_mkdir(os.path.join(script_dir, 'results', args.name))
        soft_mkdir(os.path.join(script_dir, 'results', args.name, 'docking_results'))
        soft_mkdir(os.path.join(script_dir, 'results', args.name, 'docking_small_results'))


    setup()
    savepath = os.path.join(script_dir, 'results', args.name)
    soft_mkdir(savepath)

    # Save experiment parameters
    dumper = Dumper(dumping_path=os.path.join(savepath, 'experiment.json'), dic=args.__dict__)
    dumper.dump()

    params_gentrain = {'savepath': savepath,
                       'epochs': args.epochs,
                       'device': device,
                       'lr': args.learning_rate,
                       'clip_grad': args.clip_grad_norm,
                       'beta': args.beta,
                       'processes': args.procs,
                       'optimizer': args.opti,
                       'scheduler': args.sched,
                       'gamma': -1000,
                       'DEBUG': True}
    dumper = Dumper(dumping_path=os.path.join(savepath, 'params_gentrain.json'), dic=params_gentrain)
    dumper.dump()

    prior_model_init = model_from_json(args.prior_name)
    torch.save(prior_model_init.state_dict(), os.path.join(savepath, "weights.pth"))

    for iteration in range(1, args.iters + 1):
        # SAMPLING
        sampler_main(prior_name=args.prior_name,
                     name=args.name,
                     max_samples=args.max_samples,
                     oracle=args.oracle)

        # DOCKING
        docker_main(server=args.server,
                    exhaustiveness=args.ex,
                    name=args.name,
                    oracle=args.oracle)

        # AGGREGATION AND TRAINING
        trainer_main(prior_name=args.prior_name,
                     name=args.name,
                     iteration=iteration,
                     quantile=args.quantile,
                     uncertainty=args.uncertainty,
                     oracle=args.oracle)