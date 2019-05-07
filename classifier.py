#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# PROGRAMMER: Pablo E. Hernandez
# DATE CREATED: 2019-05-02
# REVISED DATE:
# PURPOSE: Build a Neural Network to classify flower images.

from os import path
from torch import nn
from torch import optim
from torch import utils
from torchvision import datasets
from torchvision import models
from torchvision import transforms


class Classifier(nn.Module):
    """Custom Neural Network for Flower Image Classifier.
    Udacity - AI Programming with Python Nanodegree Program (ND089) Final Project
    """

    def __init__(self, data_dir=None, output_units=102, architecture='vgg16', epochs=1, hidden_units=512,
                 learning_rate=0.001, dropout=0.2, use_gpu=True, category_names_file=None):
        """Builds a pre-trained Neural Network based on the architecture model specified.

        :param data_dir: Path to root directory containing images. It is assumed 'test', 'train', and 'valid'
            sub-directories exist to be used in the different stages of the network preparation. If not specified
            the network can't be trained; however, it could be used for classification.
        :param output_units: The number of output units required for the neural network.
        :param architecture: Base architecture name. Valid options are from the torchvision.models set, which
            have been pre-trained with ImageNet data set. Sample options: resnet18, alexnet, vgg16, densenet, etc.
            Default value is vgg16
        :param epochs: The number of epochs to use during classifier training.
        :param hidden_units: The number of hidden units to be used for classifier training.
        :param learning_rate: The learning rate to be used during classifier training.
        :param dropout: The model's dropout level required to prevent neural network from overfitting.
        :param use_gpu: Indicates whether GPU should be used, if at all available.
        :param category_names_file: text filename containing class-to-name mapping in JSON format.
        """
        super(Classifier, self).__init__()

        # Keep all model's run-time settings in a dictionary in order to make it simpler to save/load model
        # checkpoints. The config attribute provides a single-point-of-entry for all Network configuration settings
        # that need to be persisted in a checkpoint.
        self.config = {
            'architecture': architecture,
            'dropout': float(dropout),
            'epochs': int(epochs),
            'hidden_units': int(hidden_units),
            'learning_rate': float(learning_rate),
            'input_units': 1,  # To be set during network initialization based on architecture.
            'output_units': int(output_units),
        }

        # Instance agnostic elements, no need to save-to/load-from checkpoint.
        self.criterion = nn.NLLLoss()
        self.data_dirs = self._get_data_directories(data_dir)
        self.data_transforms = self._get_data_transforms()
        self.data_sets = self._get_image_datasets()
        self.data_loaders = self._get_data_loaders()

        # Class-level attributes declaration and initialization...
        # The initialization method is encapsulated so that it can be called after checkpoint reload.
        self.model = None
        self.optimizer = None
        self._initialize_network()

    @staticmethod
    def _get_data_directories(data_dir):
        """Sets the paths to test, training and validation directories based on the (root) data_dir specified.

        :param data_dir: Path to root directory containing images. It is assumed 'test', 'train', and 'valid'
            sub-directories exist to be used in the different stages of the network preparation.
        :return: A dictionary containing the path to the test, training and validation image directories.
        """
        data_dirs = {
            'test': path.join(data_dir, 'test'),
            'train': path.join(data_dir, 'train'),
            'valid': path.join(data_dir, 'valid'),
        }

        # Check the existence of all required sub-directories.
        for ds in data_dirs:
            if not path.isdir(data_dirs[ds]):
                raise NotADirectoryError(f'Directory "{data_dirs[ds]}" does not exist for the "{ds}" data set.')
        return data_dirs

    def _get_image_datasets(self):
        """Loads the datasets using ImageFolder method.

        :return: the image datasets loaded with ImageFolder method.
        """
        return {
            'test':  datasets.ImageFolder(self.data_dirs['test'],  transform=self.data_transforms['test']),
            'train': datasets.ImageFolder(self.data_dirs['train'], transform=self.data_transforms['train']),
            'valid': datasets.ImageFolder(self.data_dirs['valid'], transform=self.data_transforms['valid']),
        }

    def _get_data_loaders(self):
        """Defines the dataloaders using the defined datasets.

        :return: The dataloaders used to retrieve the images for training, validation and testing.
        """
        return {
            'test':  utils.data.DataLoader(self.data_sets['test'],  batch_size=64),
            'train': utils.data.DataLoader(self.data_sets['train'], batch_size=64, shuffle=True),
            'valid': utils.data.DataLoader(self.data_sets['valid'], batch_size=64),
        }

    @staticmethod
    def _get_data_transforms():
        """Defines the transforms for the training, validation, and testing sets.

        The pre-trained networks were trained on the ImageNet dataset where each color channel was normalized
        separately. All three sets, the means, and standard deviations of the images are normalized to what the network
        expects. For the means, it's [0.485, 0.456, 0.406] and for the standard deviations [0.229, 0.224, 0.225],
        calculated from the ImageNet images. These values will shift each color channel to be centered at 0 and range
        from -1 to 1.

        :return: the transforms dictionary for the training, validation, and testing sets.
        """
        return {
            'train': transforms.Compose([transforms.RandomRotation(30),
                                         transforms.RandomResizedCrop(224),
                                         transforms.RandomHorizontalFlip(),
                                         transforms.ToTensor(),
                                         ]),

            'valid': transforms.Compose([transforms.Resize(255),
                                         transforms.CenterCrop(224),
                                         transforms.ToTensor(),
                                         transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                                         ]),

            'test': transforms.Compose([transforms.Resize(255),
                                        transforms.CenterCrop(224),
                                        transforms.ToTensor(),
                                        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
                                        ])
        }

    def _get_model(self):
        """Builds the actual model to be used in the classifier of our Neural Network. The feature parameters will
        be frozen and a custom classifier will be added for training.

        :return: The pre-trained model with frozen features and custom classifier.
        """
        try:
            model_factory = getattr(models, self.config['architecture'])
        except AttributeError:
            raise ValueError(f'Unknown model architecture {self.config["architecture"]}.')

        # Instantiate the required model.
        model = model_factory(pretrained=True)

        # Freeze the features parameters of the pre-trained network, we will only be training the classifier.
        for param in model.parameters():
            param.requires_grad = False

        # Define the custom classifier for training.
        clr = nn.Sequential(
            nn.Linear(self.config['input_units'], self.config['hidden_units']),
            nn.ReLU(),
            nn.Dropout(p=self.config['dropout']),
            nn.Linear(self.config['hidden_units'], self.config['output_units']),
            nn.LogSoftmax(dim=1))

        # Attach the custom classifier to the model.
        model.classifier = clr

        # Return the created model.
        return model

    def _initialize_network(self):
        """Initializes the Neural Network with the current run-time attributes.

        This method is intended to be called during object construction or alternatively after a checkpoint has been
        reloaded and potentially run-time attributes changed as per checkpoint.
        """
        self.model = self._get_model()
        self.optimizer = optim.Adam(self.model.classifier.parameters(), lr=self.config['learning_rate'])

    def forward(self, features):
        """Performs a forward pass on the Neural Network.
        """
        return self.forward(features)
