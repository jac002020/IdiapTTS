#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Idiap Research Institute, http://www.idiap.ch/
# Written by Bastian Schnell <bastian.schnell@idiap.ch>
#

# System imports.
import sys
import os
import torch
import torch.nn as nn

# Local source tree imports.
if not any(p.endswith("IdiapTTS") for p in sys.path):
    parent_dirs = os.path.realpath(__file__).split(os.sep)
    dir_itts = str.join(os.sep, parent_dirs[:parent_dirs.index("IdiapTTS") + 1])
    sys.path.append(dir_itts)  # Adds the IdiapTTS folder to the path, required to work on grid.
from src.neural_networks.pytorch import ModelHandlerPyTorch


class PhraseNeuralFilters(nn.Module):
    IDENTIFIER = "PhraseNeuralFilters"

    def __init__(self, dim_in, dim_out, hparams):
        super().__init__()
        # Store parameters.
        self.use_gpu = hparams.use_gpu
        self.dim_in = dim_in
        self.dim_out = dim_out
        self.dropout = hparams.dropout

        self.model_handler_flat = ModelHandlerPyTorch.ModelHandlerPyTorch(hparams)
        self.model_handler_flat.load_model(hparams.flat_model_path, hparams.use_gpu, hparams.learning_rate)
        self.add_module("flat_model", self.model_handler_flat.model)  # Add atom model as submodule so that parameters are properly registered.

        self.phrase_bias = torch.nn.Parameter(torch.Tensor(1).fill_(hparams.phrase_bias_init))

    def forward(self, inputs, hidden, seq_lengths, max_lenght_inputs, *_):
        output_flat, _ = self.model_handler_flat.model(inputs, hidden, seq_lengths, max_lenght_inputs)

        output_flat[..., 0].add_(self.phrase_bias)

        return output_flat, None

    def filters_forward(self, inputs, hidden, seq_lengths, max_length):
        """Get output of each filter without their superposition."""
        return self.model_handler_flat.model.filters_forward(inputs, hidden, seq_lengths, max_length)

    def set_gpu_flag(self, use_gpu):
        self.use_gpu = use_gpu
        self.model_handler_flat.use_gpu = use_gpu
        self.model_handler_flat.model.set_gpu_flag(use_gpu)

    def init_hidden(self, batch_size=1):
        self.model_handler_flat.model.init_hidden(batch_size)
        return None

    def thetas_approx(self):
        return self.model_handler_flat.model.thetas_approx()
