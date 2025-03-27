from lebenchmark_prepare import prepare_lebenchmark

base_dir = '/lustre/fsn1/projects/rech/nkp/uaj64gk/LeBenchmark/all_outputs'

tr_splits = [
    # small 1k
    base_dir + '/MultilingualLibriSpeech/mls_french/train',
    # medium-clean – 2.7k
    base_dir + '/EPAC_flowbert/output_waves', 
    # medium – 3k
    base_dir + '/African_Accented_French/wavs',
    base_dir + '/Att-HACK_SLR88/wavs',
    base_dir + '/CaFE/wavs',
    base_dir + '/CFPP_corrected/output',
    base_dir + '/ESLO2/ESLO/wav_turns',
    base_dir + '/GEMEP/wavs',
    base_dir + '/MPF/output_waves',
    base_dir + '/Portmedia/PMDOM2FR_wavs',
    base_dir + '/TCOF_corrected/output',
    # large - 7k
    base_dir + '/Mass/output_waves',
    base_dir + '/NCCFr/output_waves',
    base_dir + '/Voxpopuli_transcribed/wav',
    base_dir + '/Voxpopuli_unlabeled_fr/wav',
    # # extra-large - 14k
    # base_dir + '/audiocite_with_metadata/wavs',
    # base_dir + '/Niger-mali-audio-collection/output_wav',
]


dev_splits = [
    base_dir + '/MultilingualLibriSpeech/mls_french/dev',
]

te_splits = [
    base_dir + '/MultilingualLibriSpeech/mls_french/test',
]

merge_lst = tr_splits
merge_name = "train.csv"
save_folder = '/gpfswork/rech/nkp/uaj64gk/growth/prep_lebench/csvs/lg'
prepare_lebenchmark(
    save_folder, 
    tr_splits, 
    dev_splits, 
    te_splits, 
    merge_lst, 
    merge_name
)