#!/bin/bash

#SBATCH --job-name=prep_lebench   # nom du job
#SBATCH --account=dha@cpu
#SBATCH --partition=cpu_p1
#SBATCH --cpus-per-task=32
#SBATCH --time=10:00:00          # temps d'exécution maximum demande (HH:MM:SS) 
#SBATCH --output=log/prep_ll_md_%j.log  # log file


########## small 1k ##########

echo 'moving mls_french'
if [ -f "$SCRATCH/LeBenchmark/mls_french.tar.gz" ]; then
    echo "Already moved. Skipping move."
else
    scp -r -3  /lustre/fsmisc/dataset/MultilingualLibriSpeech/mls_french.tar.gz $SCRATCH/LeBenchmark
fi

if [ -d "$SCRATCH/LeBenchmark/EPAC_flowbert/output_waves" ]; then
    echo "Files already unpacked. Skipping extraction."
else
    echo 'unpacking mls_french...'
    tar -xzf $SCRATCH/LeBenchmark/mls_french.tar.gz
    echo 'done unpacking mls_french!'
fi

########## medium-clean – 2.7k ##########

echo 'moving EPAC'
if [ -d "$SCRATCH/LeBenchmark/EPAC_flowbert" ]; then
    echo "Already moved. Skipping move."
else
    scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/automatic_transc/EPAC_flowbert $SCRATCH/LeBenchmark
fi

if [ -d "$SCRATCH/LeBenchmark/EPAC_flowbert/output_waves" ]; then
    echo "Files already unpacked. Skipping extraction."
else
    echo "Unpacking EPAC..."
    tar -xf $SCRATCH/LeBenchmark/EPAC_flowbert/output_waves.tar
    echo "Done unpacking EPAC!"
fi

########## medium - 3k ##########

### African_Accented_French ###
echo 'moving African_Accented_French'
if [ -d "$SCRATCH/LeBenchmark/African_Accented_French" ]; then
    echo "Files already unpacked. Skipping extraction."
else
    scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/African_Accented_French $SCRATCH/LeBenchmark
    echo 'unpacking African_Accented_French...'
    tar -xf $SCRATCH/LeBenchmark/African_Accented_French/wavs.tar
    echo 'done unpacking African_Accented_French!'
fi

### Att-HACK_SLR88 ###
echo 'moving Att-HACK_SLR88'
if [ -d "$SCRATCH/LeBenchmark/Att-HACK_SLR88" ]; then
    echo "Files already unpacked. Skipping extraction."
else
    scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/Att-HACK_SLR88 $SCRATCH/LeBenchmark
    echo 'unpacking Att-HACK_SLR88...'
    tar -xf $SCRATCH/LeBenchmark/Att-HACK_SLR88/wavs.tar
    echo 'done unpacking Att-HACK_SLR88!'
fi

### CaFE ###
echo 'moving CaFE'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/CaFE $SCRATCH/LeBenchmark
echo 'unpacking CaFE...'
tar -xf $SCRATCH/LeBenchmark/CaFE/wavs.tar
echo 'done unpacking CaFE!'

### CFPP_corrected ###
echo 'moving CFPP_corrected'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/CFPP_corrected $SCRATCH/LeBenchmark
echo 'unpacking CFPP_corrected...'
tar -xf $SCRATCH/LeBenchmark/CFPP_corrected/output.tar
echo 'done unpacking CFPP_corrected!'

### ESLO2 ###
echo 'moving ESLO2'
scp -r -3 /lustre/fsstor/projects/rech/nkp/uaj64gk/LeBenchmark/eslo2_train1_flowbert.tar.gz $SCRATCH/LeBenchmark
echo 'unpacking ESLO2...'
tar -xf $SCRATCH/LeBenchmark/eslo2_train1_flowbert.tar.gz
echo 'done unpacking ESLO2!'

### GEMEP ###
echo 'moving GEMEP'
rsync -av --exclude 'ESLO/' --exclude 'Scripts/' /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/GEMEP $SCRATCH/LeBenchmark
echo 'unpacking GEMEP...'
tar -xf $SCRATCH/LeBenchmark/GEMEP/wavs.tar
echo 'done unpacking GEMEP!'

### MPF ###
echo 'moving MPF'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/MPF $SCRATCH/LeBenchmark
echo 'unpacking MPF...'
tar -xf $SCRATCH/LeBenchmark/MPF/output_waves.tar
echo 'done unpacking MPF!'

### Portmedia ###
echo 'moving Portmedia'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/Portmedia $SCRATCH/LeBenchmark
echo 'unpacking Portmedia...'
tar -xf $SCRATCH/LeBenchmark/Portmedia/PMDOM2FR_wavs.tar
echo 'done unpacking Portmedia!'

### TCOF_corrected ###
echo 'moving TCOF_corrected'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/TCOF_corrected $SCRATCH/LeBenchmark
echo 'unpacking TCOF_corrected...'
tar -xf $SCRATCH/LeBenchmark/Portmedia/output.tar.tar
echo 'done unpacking TCOF_corrected!'



########## large - 7k ##########
### MaSS ###
echo 'moving MaSS'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v2/SpeechData/raw_datasets/Mass $SCRATCH/LeBenchmark
echo 'unpacking Mass...'
tar -xf $SCRATCH/LeBenchmark/Mass/output_waves.tar
echo 'done unpacking Mass!'

### MaSS ###
echo 'moving NCCFr'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v2/SpeechData/raw_datasets/NCCFr $SCRATCH/LeBenchmark
echo 'unpacking NCCFr...'
tar -xf $SCRATCH/LeBenchmark/NCCFr/output_waves.tar
echo 'done unpacking NCCFr!'

### voxpopuli_unlabelled ###
echo 'moving Voxpopuli_unlabeled_fr'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/Voxpopuli_unlabeled_fr $SCRATCH/LeBenchmark
echo 'unpacking Voxpopuli_unlabeled_fr...'
tar -xf $SCRATCH/LeBenchmark/Voxpopuli_unlabeled_fr/wav.tar
echo 'done unpacking Voxpopuli_unlabeled_fr!'

### voxpopuli_transcribed_data ###
echo 'moving Voxpopuli_transcribed'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/otherTransc/Voxpopuli_transcribed $SCRATCH/LeBenchmark
echo 'unpacking Voxpopuli_transcribed...'
tar -xf $SCRATCH/LeBenchmark/Voxpopuli_transcribed/wav.tar
echo 'done unpacking Voxpopuli_transcribed!'


########## extra-large - 14k ##########

echo 'moving Niger-mali-audio-collection'
scp -r -3 /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/Niger-mali-audio-collection $SCRATCH/LeBenchmark
echo 'unpacking Niger-mali-audio-collection...'
tar -xf $SCRATCH/LeBenchmark/Niger-mali-audio-collection/output_wav.tar
echo 'done unpacking Niger-mali-audio-collection!'

echo 'moving audiocite_with_metadata'
rsync -av --include='*/' --include='*.tar' --exclude='*' /lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/audiocite_with_metadata $SCRATCH/LeBenchmark/
echo 'unpacking  audiocite_with_metadata...'
tar -xf $SCRATCH/LeBenchmark/audiocite_with_metadata/wavs.tar
echo 'done unpacking audiocite_with_metadata!'

echo "Done!"