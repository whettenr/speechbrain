# AISHELL-1 ASR with Transformers.
This folder contains recipes for tokenization and speech recognition with [AISHELL-1](https://www.openslr.org/33/), a 150-hour Chinese ASR dataset.

### How to run
1- Train a tokenizer. The tokenizer takes in input the training transcripts and determines the subword units that will be used for both acoustic and language model training.

```
cd ../../Tokenizer
python train.py hparams/train_transformer_tokenizer_bpe5000.yaml --data_folder=/path/to/aishell
```
This step is not mandatory. We will use the official tokenizer downloaded from the web if you do not
specify a different tokenizer in the speech recognition recipe.

2- Train the speech recognizer
```
python train.py hparams/train_ASR_transformer.yaml --data_folder=/localscratch/aishell/
```

Make sure to have `transformers` installed if you use the wav2vec2 recipe (see extra-requirements.txt)

# Performance summary
Results are reported in terms of Character Error Rate (CER).

| hyperparams file | LM | Test CER | Dev CER | GPUs |
|:--------------------------:|:-----:| :-----:| :-----:| :-----: |
| train_ASR_transformer.yaml | No | 6.04 | 5.60 | 1xRTX 2080 Ti 11GB |
| train_ASR_transformer_with_wav2vect.yaml | No | 5.58 | 5.19 | 1xRTX 8000 Ti 48GB |

You can checkout our results (models, training logs, etc,) here:
https://www.dropbox.com/sh/tp6tjmysorgvsr4/AAD7KNqi1ot0gR4N406JbKM6a?dl=0

# Training Time
It takes about 1h 10 minutes on a NVIDIA V100 (32GB) for train_ASR_transformer.yaml,
and about 5 hours minutes on a NVIDIA V100 (32GB) for rain_ASR_transformer_with_wav2vect.yaml.


# PreTrained Model + Easy-Inference
You can find the pre-trained model with an easy-inference function on HuggingFace
- https://huggingface.co/speechbrain/asr-transformer-aishell
- https://huggingface.co/speechbrain/asr-wav2vec2-transformer-aishell


# **About SpeechBrain**
- Website: https://speechbrain.github.io/
- Code: https://github.com/speechbrain/speechbrain/
- HuggingFace: https://huggingface.co/speechbrain/


# **Citing SpeechBrain**
Please, cite SpeechBrain if you use it for your research or business.

```bibtex
@misc{speechbrainV1,
  title={Open-Source Conversational AI with SpeechBrain 1.0},
  author={Mirco Ravanelli and Titouan Parcollet and Adel Moumen and Sylvain de Langen and Cem Subakan and Peter Plantinga and Yingzhi Wang and Pooneh Mousavi and Luca Della Libera and Artem Ploujnikov and Francesco Paissan and Davide Borra and Salah Zaiem and Zeyu Zhao and Shucong Zhang and Georgios Karakasidis and Sung-Lin Yeh and Pierre Champion and Aku Rouhe and Rudolf Braun and Florian Mai and Juan Zuluaga-Gomez and Seyed Mahed Mousavi and Andreas Nautsch and Xuechen Liu and Sangeet Sagar and Jarod Duret and Salima Mdhaffar and Gaelle Laperriere and Mickael Rouvier and Renato De Mori and Yannick Esteve},
  year={2024},
  eprint={2407.00463},
  archivePrefix={arXiv},
  primaryClass={cs.LG},
  url={https://arxiv.org/abs/2407.00463},
}
@misc{speechbrain,
  title={{SpeechBrain}: A General-Purpose Speech Toolkit},
  author={Mirco Ravanelli and Titouan Parcollet and Peter Plantinga and Aku Rouhe and Samuele Cornell and Loren Lugosch and Cem Subakan and Nauman Dawalatabad and Abdelwahab Heba and Jianyuan Zhong and Ju-Chieh Chou and Sung-Lin Yeh and Szu-Wei Fu and Chien-Feng Liao and Elena Rastorgueva and François Grondin and William Aris and Hwidong Na and Yan Gao and Renato De Mori and Yoshua Bengio},
  year={2021},
  eprint={2106.04624},
  archivePrefix={arXiv},
  primaryClass={eess.AS},
  note={arXiv:2106.04624}
}
```
