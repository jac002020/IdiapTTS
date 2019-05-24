# IdiapTTS
This repository contains the Idiap Text-to-Speech system developed at the [Idiap Research Institute](https://www.idiap.ch/en), Martigny, Switzerland.  
Contact: <bastian.schnell@idiap.ch>

It is an almost purely Python-based modular toolbox for building Deep Neural Network models (using [PyTorch](https://pytorch.org/)) for statistical parametric speech synthesis. It provides scripts for feature extraction and preparation which are based on third-party tools (e.g. [Festival](http://www.cstr.ed.ac.uk/projects/festival/)). It uses the [WORLD](https://github.com/mmorise/World) vocoder (i.e. its [Python wrapper](https://github.com/JeremyCCHsu/Python-Wrapper-for-World-Vocoder)) for waveform generation. The framework was highly inspired by [Merlin](https://github.com/CSTR-Edinburgh/merlin) and reuses some of its data preparation functionalities. In contrast to Merlin it is intended to be more modular and allowing prototyping purely in Python.

It comes with recipes in the spirit of [Kaldi](https://github.com/kaldi-asr/kaldi) located in the *egs* directory.

IdiapTTS is distributed under the MIT license, allowing unrestricted commercial and non-commercial use.

IdiapTTS is tested with: **Python 3.6**

## Installation
Follow the instructions given in *INSTALL.md*.

## Publications
#### Icassp'19: An End-to-End Network to Synthesize Intonation using a Generalized Command Response Model
Instructions to reproduce the results of the paper can be found in *egs/blizzard08_roger/s2/*.