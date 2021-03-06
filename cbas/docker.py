"""
Script to be called by a job array slurm task.
Takes the path to a csv and annotate it with docking scores
"""
import os
import sys
import argparse
import pandas as pd
import csv
import numpy as np
import pickle
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import QED
from functools import partial

script_dir = os.path.dirname(os.path.realpath(__file__))
if __name__ == '__main__':
    sys.path.append(os.path.join(script_dir, '..'))

from docking.docking import dock, set_path
from data_processing.comp_metrics import cLogP, cQED


def one_slurm(list_smiles, server, unique_id, name, target='drd3', parallel=True, exhaustiveness=16, mean=False,
              load=False):
    """

    :param list_smiles:
    :param server:
    :param unique_id:
    :param name:
    :param parallel:
    :param exhaustiveness:
    :param mean:
    :param load:
    :return:
    """
    pythonsh, vina = set_path(server)
    dirname = os.path.join(script_dir, 'results', name, 'docking_small_results')
    dump_path = os.path.join(dirname, f"{unique_id}.csv")

    header = ['smile', 'score']
    with open(dump_path, 'w', newline='') as csvfile:
        csv.writer(csvfile).writerow(header)

    for smile in list_smiles:
        score_smile = dock(smile, target='drd3', unique_id=unique_id, parallel=parallel, exhaustiveness=exhaustiveness,
                           mean=mean,
                           pythonsh=pythonsh, vina=vina, load=load)
        # score_smile = 0
        with open(dump_path, 'a', newline='') as csvfile:
            list_to_write = [smile, score_smile]
            csv.writer(csvfile).writerow(list_to_write)


def one_slurm_qed(list_smiles, unique_id, name):
    """

    :param list_smiles:
    :param unique_id:
    :param name:
    :return:
    """
    dirname = os.path.join(script_dir, 'results', name, 'docking_small_results')
    dump_path = os.path.join(dirname, f"{unique_id}.csv")

    header = ['smile', 'score']
    with open(dump_path, 'w', newline='') as csvfile:
        csv.writer(csvfile).writerow(header)

    for smile in list_smiles:
        m = Chem.MolFromSmiles(smile)
        if m is not None:
            score_smile = QED.qed(m)
        else:
            score_smile = 0
        with open(dump_path, 'a', newline='') as csvfile:
            list_to_write = [smile, score_smile]
            csv.writer(csvfile).writerow(list_to_write)


def one_slurm_composite(list_smiles, unique_id, name, oracle):
    """

    :param list_smiles:
    :param unique_id:
    :param name:
    :return:
    """
    dirname = os.path.join(script_dir, 'results', name, 'docking_small_results')
    dump_path = os.path.join(dirname, f"{unique_id}.csv")
    assert oracle in ['cqed', 'clogp']

    header = ['smile', 'score']
    with open(dump_path, 'w', newline='') as csvfile:
        csv.writer(csvfile).writerow(header)

    for smile in list_smiles:
        if oracle == 'clogp':
            score_smile = cLogP(smile, errorVal=-100)  # invalid smiles get score -100
        else:
            score_smile = cQED(smile, errorVal=-20)
        with open(dump_path, 'a', newline='') as csvfile:
            list_to_write = [smile, score_smile]
            csv.writer(csvfile).writerow(list_to_write)


def one_slurm_qsar(list_smiles, unique_id, name):
    """
    :param list_smiles:
    :param unique_id:
    :param name:
    :return:
    """
    # TODO: IMPLEMENT
    raise NotImplementedError

    dirname = os.path.join(script_dir, 'results', name, 'docking_small_results')
    dump_path = os.path.join(dirname, f"{unique_id}.csv")

    header = ['smile', 'score']
    with open(dump_path, 'w', newline='') as csvfile:
        csv.writer(csvfile).writerow(header)

    for smile in list_smiles:
        m = Chem.MolFromSmiles(smile)
        if m is not None:
            score_smile = QED.qed(m)
        else:
            score_smile = 0
        with open(dump_path, 'a', newline='') as csvfile:
            list_to_write = [smile, score_smile]
            csv.writer(csvfile).writerow(list_to_write)


def main(proc_id, num_procs, server, exhaustiveness, name, oracle, target):
    # parse the docking task of the whole job array and split it
    dump_path = os.path.join(script_dir, 'results', name, 'docker_samples.p')
    list_smiles = pickle.load(open(dump_path, 'rb'))

    N = len(list_smiles)
    chunk_size, rab = N // num_procs, N % num_procs
    chunk_min, chunk_max = proc_id * chunk_size, min((proc_id + 1) * chunk_size, N)
    list_data = list_smiles[chunk_min:chunk_max]
    # N = chunk_size*num_procs + rab
    # Share rab between procs
    if proc_id < rab:
        list_data.append(list_smiles[-(proc_id + 1)])

    # Just use qed
    if oracle == 'qed':
        one_slurm_qed(list_data, proc_id, name)

    elif oracle in ['clogp', 'cqed']:  # composite logp or composite qed
        one_slurm_composite(list_data, proc_id, name, oracle)

    # Do the docking and dump results
    elif oracle == 'docking':
        one_slurm(list_data,
                  target=target,
                  name=name,
                  server=server,
                  unique_id=proc_id,
                  parallel=False,
                  exhaustiveness=exhaustiveness,
                  mean=True)
    else:
        raise ValueError(f'oracle {oracle} not implemented')


def one_dock(smile, server, parallel=False, exhaustiveness=16, mean=False, load=False, target='drd3'):
    pythonsh, vina = set_path(server)
    score_smile = dock(smile, unique_id=smile, parallel=parallel, exhaustiveness=exhaustiveness, mean=mean,
                       pythonsh=pythonsh, vina=vina, load=load, target=target)

    return score_smile


def one_qed(smile):
    m = Chem.MolFromSmiles(smile)
    return 0 if m is None else QED.qed(m)


def one_fp(smile):
    m = Chem.MolFromSmiles(smile)
    if m is not None:
        fp = AllChem.GetMorganFingerprintAsBitVect(m, 3,
                                                   nBits=2048)  # careful radius = 3 equivalent to ECFP 6 (diameter = 6, radius = 3)
        fp = np.array(fp)
        return fp
    return None


def one_node_main(server, exhaustiveness, name, oracle, target='drd3'):
    from multiprocessing import Pool

    # parse the docking task of the whole job array and split it
    load_path = os.path.join(script_dir, 'results', name, 'docker_samples.p')
    list_smiles = pickle.load(open(load_path, 'rb'))

    p = Pool(20)
    # Just use qed
    if oracle == 'qed':
        list_results = p.map(one_qed, list_smiles)
        p.close()

    elif oracle == 'clogp':
        list_results = p.map(cLogP, list_smiles)
        p.close()

    elif oracle == 'cqed':
        list_results = p.map(cQED, list_smiles)
        p.close()

    elif oracle == 'qsar':
        list_fps = p.map(one_fp, list_smiles)
        filtered_smiles = list()
        filtered_fps = list()
        for i, fp in enumerate(list_fps):
            if fp is not None:
                filtered_smiles.append(list_smiles[i])
                filtered_fps.append(fp)
        list_smiles = filtered_smiles
        input_array = np.vstack(filtered_fps)
        svm_model = pickle.load(
            open(os.path.join(script_dir, '..', 'results', 'saved_models', 'qsar_svm.pickle'), 'rb'))
        list_results = svm_model.predict_proba(input_array)[:, 1]
    elif oracle == 'docking':
        list_results = p.map(partial(one_dock,
                                     server=server,
                                     parallel=False,
                                     exhaustiveness=exhaustiveness,
                                     mean=True,
                                     load=False,
                                     target=target), list_smiles)
    else:
        raise ValueError(f'oracle {oracle} not implemented')

    dump_path = os.path.join(script_dir, 'results', name, 'docking_small_results', '0.csv')
    df = pd.DataFrame.from_dict({'smile': list_smiles, 'score': list_results})
    df.to_csv(dump_path)


if __name__ == '__main__':
    pass

    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--server", default='mac', help="Server to run the docking on, for path and configs.")
    parser.add_argument("-ex", "--exhaustiveness", default=64, help="exhaustiveness parameter for vina")
    parser.add_argument("-n", "--name", default='search_vae', help="Name of the exp")
    parser.add_argument('--oracle', type=str)  # 'qed' or 'docking' or 'qsar'
    parser.add_argument('--target', type=str, default='drd3')
    args, _ = parser.parse_known_args()

    try:
        proc_id, num_procs = int(sys.argv[1]), int(sys.argv[2])
    except IndexError:
        print('We are not using the args as usually in docker.py')
        proc_id, num_procs = 2, 10
    except ValueError:
        print('We are not using the args as usually in docker.py')
        proc_id, num_procs = 2, 10

    main(proc_id=proc_id,
         num_procs=num_procs,
         server=args.server,
         exhaustiveness=args.exhaustiveness,
         name=args.name,
         oracle=args.oracle,
         target=args.target)
