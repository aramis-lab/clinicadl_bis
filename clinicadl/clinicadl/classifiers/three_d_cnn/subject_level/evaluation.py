from __future__ import print_function
import argparse
import os
from os import path
import pandas as pd
import torch.nn as nn
from torch.utils.data import DataLoader

from classifiers.three_d_cnn.subject_level.utils import test
from tools.deep_learning.data import MRIDataset, MinMaxNormalization, load_data
from tools.deep_learning import create_model, load_model, read_json

parser = argparse.ArgumentParser(description="Argparser for evaluation of classifiers")

# Mandatory arguments
parser.add_argument("model_path", type=str,
                    help="Path to the trained model folder.")

# Model selection
parser.add_argument("--selection_eval", default="loss", type=str, choices=['loss', 'accuracy'],
                    help="Loads the model selected on minimal loss or maximum accuracy on validation.")

# Computational ressources
parser.add_argument("--gpu", action="store_true", default=False,
                    help="if True computes the visualization on GPU")
parser.add_argument('--num_threads', type=int, default=0,
                    help='Number of threads used.')
parser.add_argument("--num_workers", '-w', default=8, type=int,
                    help='the number of batch being loaded in parallel')


if __name__ == "__main__":
    ret = parser.parse_known_args()
    options = ret[0]
    if ret[1]:
        print("unknown arguments: %s" % parser.parse_known_args()[1])

    # Loop on all folds trained
    model_dir = path.join(options.model_path, 'best_model_dir')
    folds_dir = os.listdir(model_dir)
    for fold_dir in folds_dir:
        split = int(fold_dir[-1])
        options.split = split
        options = read_json(options, "CNN")

        print("Fold " + str(split))
        model = create_model(options.model)

        criterion = nn.CrossEntropyLoss()

        if options.selection_eval == 'loss':
            model_dir = path.join(model_dir, fold_dir, 'CNN', 'best_loss')
            folder_name = 'best_loss'
        else:
            model_dir = path.join(model_dir, fold_dir, 'CNN', 'best_acc')
            folder_name = 'best_acc'

        best_model, best_epoch = load_model(model, model_dir, options.gpu,
                                            filename='model_best.pth.tar')

        training_tsv, valid_tsv = load_data(options.diagnosis_path, options.diagnoses,
                                            split, options.n_splits, options.baseline)

        if options.minmaxnormalization:
            transformations = MinMaxNormalization()
        else:
            transformations = None

        data_train = MRIDataset(options.input_dir, training_tsv, options.preprocessing, transform=transformations)
        data_valid = MRIDataset(options.input_dir, valid_tsv, options.preprocessing, transform=transformations)

        # Use argument load to distinguish training and testing
        train_loader = DataLoader(data_train,
                                  batch_size=options.batch_size,
                                  shuffle=False,
                                  num_workers=options.num_workers,
                                  drop_last=False
                                  )

        valid_loader = DataLoader(data_valid,
                                  batch_size=options.batch_size,
                                  shuffle=False,
                                  num_workers=options.num_workers,
                                  drop_last=False
                                  )

        metrics_train, loss_train, train_df = test(best_model, train_loader, options.gpu, criterion, full_return=True)
        metrics_valid, loss_valid, valid_df = test(best_model, valid_loader, options.gpu, criterion, full_return=True)

        acc_train, sen_train, spe_train = metrics_train['balanced_accuracy'] * 100, metrics_train['sensitivity'] * 100,\
                                          metrics_train['specificity'] * 100
        acc_valid, sen_valid, spe_valid = metrics_valid['balanced_accuracy'] * 100, metrics_valid['sensitivity'] * 100, \
                                          metrics_valid['specificity'] * 100
        print("Training, acc %f, loss %f, sensibility %f, specificity %f"
              % (acc_train, loss_train, sen_train, spe_train))
        print("Validation, acc %f, loss %f, sensibility %f, specificity %f"
              % (acc_valid, loss_valid, sen_valid, spe_valid))

        evaluation_path = path.join(options.model_path, 'performances', fold_dir)
        if not path.exists(path.join(evaluation_path, folder_name)):
            os.makedirs(path.join(evaluation_path, folder_name))

        train_df.to_csv(path.join(evaluation_path, folder_name, 'train_subject_level_result.tsv'), sep='\t', index=False)
        valid_df.to_csv(path.join(evaluation_path, folder_name, 'valid_subject_level_result.tsv'), sep='\t', index=False)

        pd.DataFrame(metrics_train, index=[0]).to_csv(path.join(evaluation_path, folder_name,
                                                                'train_subject_level_metrics.tsv'),
                                                      sep='\t', index=False)
        pd.DataFrame(metrics_valid, index=[0]).to_csv(path.join(evaluation_path, folder_name,
                                                                'valid_subject_level_metrics.tsv'),
                                                      sep='\t', index=False)
