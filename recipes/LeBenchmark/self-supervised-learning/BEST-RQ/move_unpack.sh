#!/bin/bash

#SBATCH --job-name=prep_lebench   # nom du job
#SBATCH --account=dha@cpu
#SBATCH --partition=prepost
#SBATCH --time=2:00:00
#SBATCH --output=log/prep_med_%j.log


# List of directories and corresponding file names
DIRECTORIES=(
    # # sm
    # "/lustre/fsmisc/dataset/MultilingualLibriSpeech/mls_french.tar.gz"
    # # md-clean
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/automatic_transc/EPAC_flowbert/output_waves.tar"
    # # md
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/African_Accented_French/wavs.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/Att-HACK_SLR88/wavs.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/CaFE/wavs.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/CFPP_corrected/output.tar"
    # "/lustre/fsstor/projects/rech/nkp/uaj64gk/LeBenchmark/ESLO2/eslo2_train1_flowbert.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/GEMEP/wavs.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/MPF/output_waves.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/Portmedia/PMDOM2FR_wavs.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/aligned/manual_transc/TCOF_corrected/output.tar"
    # # lg
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v2/SpeechData/raw_datasets/Mass/output_waves.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v2/SpeechData/raw_datasets/NCCFr/output_waves.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/Voxpopuli_unlabeled_fr/wav.tar"
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/otherTransc/Voxpopuli_transcribed/wav.tar"
    # # xlg
    # "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/Niger-mali-audio-collection/output_wav.tar"
    "/lustre/fsstor/projects/rech/oou/commun/pretraining_data/Panta_v1/SpeechData/unTransc/audiocite_with_metadata/wavs.tar"
)


SCRATCH_DIR="$SCRATCH/LeBenchmark"
OUTPUT_DIR="$SCRATCH_DIR/all_outputs"

# check if exists
for DIR in "${DIRECTORIES[@]}"; do
    if [ ! -e "$DIR" ]; then
        echo "Error: File $DIR does not exist. Skipping."
        continue
    else 
        echo "file $DIR exists!"
    fi
done

mkdir -p "$OUTPUT_DIR"

for DIR in "${DIRECTORIES[@]}"; do
    # get second to last in file path
    PARENT_DIR=$(basename $(dirname "$DIR")) 
    # make directory using name
    mkdir -p "$OUTPUT_DIR/$PARENT_DIR"
    # location of dir where files will be unpacked
    OUTPUT_PATH="$OUTPUT_DIR/$PARENT_DIR"
    # name of new .tar file
    FILE_PATH="$OUTPUT_PATH/$(basename "$DIR")"

    echo "Processing $DIR..."

    if [ -e "$FILE_PATH" ]; then
        echo "$DIR already moved to $FILE_PATH. Skipping move."
    else
        echo "Copying $DIR to $FILE_PATH ..."
        scp -r -3 "$DIR" "$FILE_PATH"
    fi

    # Check file ending
    if [[ "$FILE_PATH" == *.tar.gz ]]; then
        # Check if the extracted directory already exists
        if [ -d "$OUTPUT_PATH/$(basename "$FILE_PATH" .tar.gz)" ]; then
            echo "$OUTPUT_PATH already unpacked. Skipping extraction."
        else
            echo "Unpacking $PARENT_DIR..."
            tar -xf "$FILE_PATH" -C "$OUTPUT_PATH"
        fi
    elif [[ "$FILE_PATH" == *.tar ]]; then
        # Check if the extracted directory already exists
        if [ -d "$OUTPUT_PATH/$(basename "$FILE_PATH" .tar)" ]; then
            echo "$OUTPUT_PATH already unpacked. Skipping extraction."
        else
            echo "Unpacking $PARENT_DIR..."
            tar -xf "$FILE_PATH" -C "$OUTPUT_PATH"
        fi
    fi 
    echo "Done processing $PARENT_DIR."
done



# ###### test
# SCRATCH_DIR="$SCRATCH/LeBenchmark"
# OUTPUT_DIR="$SCRATCH_DIR/all_outputs"
# DIR=/lustre/fsmisc/dataset/MultilingualLibriSpeech/mls_french.tar.gz
# PARENT_DIR=$(basename $(dirname "$DIR")) 
# # make directory using name
# mkdir -p "$OUTPUT_DIR/$PARENT_DIR"
# # location of dir where files will be unpacked
# OUTPUT_PATH="$OUTPUT_DIR/$PARENT_DIR"
# # name of new .tar file
# FILE_PATH="$OUTPUT_PATH/$(basename "$DIR")"

# echo "Processing $DIR..."

# if [ -e "$FILE_PATH" ]; then
#     echo "$DIR already moved to $FILE_PATH. Skipping move."
# else
#     echo "Copying $DIR to $FILE_PATH ..."
#     # scp -r -3 "$DIR" "$FILE_PATH"
# fi

# # Check file ending
# if [[ "$FILE_PATH" == *.tar.gz ]]; then
#     # Check if the extracted directory already exists
#     if [ -d "$OUTPUT_PATH/$(basename "$FILE_PATH" .tar.gz)" ]; then
#         echo "$OUTPUT_PATH already unpacked. Skipping extraction."
#     else
#         echo "Unpacking $PARENT_DIR..."
#         # tar -xf "$FILE_PATH" -C "$OUTPUT_PATH"
#     fi
# elif [[ "$FILE_PATH" == *.tar ]]; then
#     # Check if the extracted directory already exists
#     if [ -d "$OUTPUT_PATH/$(basename "$FILE_PATH" .tar)" ]; then
#         echo "$OUTPUT_PATH already unpacked. Skipping extraction."
#     else
#         echo "Unpacking $PARENT_DIR..."
#         # tar -xf "$FILE_PATH" -C "$OUTPUT_PATH"
#     fi
# fi
     
# echo "Done processing $PARENT_DIR."