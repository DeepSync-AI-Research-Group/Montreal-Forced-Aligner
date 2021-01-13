import shutil
import os
import time
import multiprocessing as mp
import yaml

from montreal_forced_aligner import __version__
from montreal_forced_aligner.corpus.align_corpus import AlignableCorpus
from montreal_forced_aligner.dictionary import Dictionary
from montreal_forced_aligner.aligner import PretrainedAligner
from montreal_forced_aligner.models import AcousticModel
from montreal_forced_aligner.config import TEMP_DIR, align_yaml_to_config, load_basic_align
from montreal_forced_aligner.utils import get_available_acoustic_languages, get_pretrained_acoustic_path, \
    get_available_dict_languages, get_dictionary_path
from montreal_forced_aligner.exceptions import ArgumentError


class DummyArgs(object):
    def __init__(self):
        self.corpus_directory = ''
        self.dictionary_path = ''
        self.acoustic_model_path = ''
        self.speaker_characters = 0
        self.num_jobs = 0
        self.verbose = False
        self.clean = True
        self.fast = True
        self.debug = False
        self.temp_directory = None
        self.config_path = ''


def align_corpus(args):
    all_begin = time.time()
    if not args.temp_directory:
        temp_dir = TEMP_DIR
    else:
        temp_dir = os.path.expanduser(args.temp_directory)
    corpus_name = os.path.basename(args.corpus_directory)
    if corpus_name == '':
        args.corpus_directory = os.path.dirname(args.corpus_directory)
        corpus_name = os.path.basename(args.corpus_directory)
    data_directory = os.path.join(temp_dir, corpus_name)
    conf_path = os.path.join(data_directory, 'config.yml')
    if os.path.exists(conf_path):
        with open(conf_path, 'r') as f:
            conf = yaml.load(f, Loader=yaml.SafeLoader)
    else:
        conf = {'dirty': False,
                'begin': time.time(),
                'version': __version__,
                'type': 'align',
                'corpus_directory': args.corpus_directory,
                'dictionary_path': args.dictionary_path}
    if getattr(args, 'clean', False) \
            or conf['dirty'] or conf['type'] != 'align' \
            or conf['corpus_directory'] != args.corpus_directory \
            or conf['version'] != __version__ \
            or conf['dictionary_path'] != args.dictionary_path:
        shutil.rmtree(data_directory, ignore_errors=True)

    os.makedirs(data_directory, exist_ok=True)
    os.makedirs(args.output_directory, exist_ok=True)
    try:
        corpus = AlignableCorpus(args.corpus_directory, data_directory,
                        speaker_characters=args.speaker_characters,
                        num_jobs=args.num_jobs)
        if corpus.issues_check:
            print('WARNING: Some issues parsing the corpus were detected. '
                  'Please run the validator to get more information.')
        print(corpus.speaker_utterance_info())
        acoustic_model = AcousticModel(args.acoustic_model_path)
        dictionary = Dictionary(args.dictionary_path, data_directory, word_set=corpus.word_set)
        acoustic_model.validate(dictionary)

        begin = time.time()
        if args.config_path:
            align_config = align_yaml_to_config(args.config_path)
        else:
            align_config = load_basic_align()
        a = PretrainedAligner(corpus, dictionary, acoustic_model, align_config,
                              temp_directory=data_directory,
                              debug=getattr(args, 'debug', False))
        if args.debug:
            print('Setup pretrained aligner in {} seconds'.format(time.time() - begin))
        a.verbose = args.verbose

        begin = time.time()
        a.align()
        if args.debug:
            print('Performed alignment in {} seconds'.format(time.time() - begin))

        begin = time.time()
        a.export_textgrids(args.output_directory)
        if args.debug:
            print('Exported TextGrids in {} seconds'.format(time.time() - begin))
        print('Done! Everything took {} seconds'.format(time.time() - all_begin))
    except Exception as _:
        conf['dirty'] = True
        raise
    finally:
        with open(conf_path, 'w') as f:
            yaml.dump(conf, f)


def custom_align_corpus(temp_directory, corpus_directory, output_directory, dictionary_path, acoustic_model_path,
                        config_path, speaker_characters, clean=False, num_jobs=0, debug = False, verbose=False):
    all_begin = time.time()
    if not temp_directory:
        temp_dir = TEMP_DIR
    else:
        temp_dir = os.path.expanduser(temp_directory)
    corpus_name = os.path.basename(corpus_directory)
    if corpus_name == '':
        corpus_directory = os.path.dirname(corpus_directory)
        corpus_name = os.path.basename(corpus_directory)
    data_directory = os.path.join(temp_dir, corpus_name)
    conf_path = os.path.join(data_directory, 'config.yml')
    if os.path.exists(conf_path):
        with open(conf_path, 'r') as f:
            conf = yaml.load(f, Loader=yaml.SafeLoader)
    else:
        conf = {'dirty': False,
                'begin': time.time(),
                'version': __version__,
                'type': 'align',
                'corpus_directory': corpus_directory,
                'dictionary_path': dictionary_path}
    if clean \
            or conf['dirty'] or conf['type'] != 'align' \
            or conf['corpus_directory'] != corpus_directory \
            or conf['version'] != __version__ \
            or conf['dictionary_path'] != dictionary_path:
        shutil.rmtree(data_directory, ignore_errors=True)

    os.makedirs(data_directory, exist_ok=True)
    os.makedirs(output_directory, exist_ok=True)
    try:
        corpus = AlignableCorpus(corpus_directory, data_directory,
                        speaker_characters=speaker_characters,
                        num_jobs=num_jobs)
        if corpus.issues_check:
            print('WARNING: Some issues parsing the corpus were detected. '
                  'Please run the validator to get more information.')
        print(corpus.speaker_utterance_info())
        acoustic_model = AcousticModel(acoustic_model_path)
        dictionary = Dictionary(dictionary_path, data_directory, word_set=corpus.word_set)
        acoustic_model.validate(dictionary)

        begin = time.time()
        if config_path:
            align_config = align_yaml_to_config(config_path)
        else:
            align_config = load_basic_align()
        a = PretrainedAligner(corpus, dictionary, acoustic_model, align_config,
                              temp_directory=data_directory,
                              debug=debug)
        if debug:
            print('Setup pretrained aligner in {} seconds'.format(time.time() - begin))
        a.verbose = verbose

        begin = time.time()
        a.align()
        if debug:
            print('Performed alignment in {} seconds'.format(time.time() - begin))

        begin = time.time()
        a.export_textgrids(output_directory)
        if debug:
            print('Exported TextGrids in {} seconds'.format(time.time() - begin))
        print('Done! Everything took {} seconds'.format(time.time() - all_begin))
    except Exception as _:
        conf['dirty'] = True
        raise
    finally:
        with open(conf_path, 'w') as f:
            yaml.dump(conf, f)



def validate_args(args, downloaded_acoustic_models, download_dictionaries):
    if not os.path.exists(args.corpus_directory):
        raise ArgumentError('Could not find the corpus directory {}.'.format(args.corpus_directory))
    if not os.path.isdir(args.corpus_directory):
        raise ArgumentError('The specified corpus directory ({}) is not a directory.'.format(args.corpus_directory))

    if args.corpus_directory == args.output_directory:
        raise ArgumentError('Corpus directory and output directory cannot be the same folder.')

    if args.dictionary_path.lower() in download_dictionaries:
        args.dictionary_path = get_dictionary_path(args.dictionary_path.lower())
    if not os.path.exists(args.dictionary_path):
        raise ArgumentError('Could not find the dictionary file {}'.format(args.dictionary_path))
    if not os.path.isfile(args.dictionary_path):
        raise ArgumentError('The specified dictionary path ({}) is not a text file.'.format(args.dictionary_path))

    if args.acoustic_model_path.lower() in downloaded_acoustic_models:
        args.acoustic_model_path = get_pretrained_acoustic_path(args.acoustic_model_path.lower())
    elif args.acoustic_model_path.lower().endswith(AcousticModel.extension):
        if not os.path.exists(args.acoustic_model_path):
            raise ArgumentError('The specified model path does not exist: ' + args.acoustic_model_path)
    else:
        raise ArgumentError(
            'The language \'{}\' is not currently included in the distribution, '
            'please align via training or specify one of the following language names: {}.'.format(
                args.acoustic_model_path.lower(), ', '.join(downloaded_acoustic_models)))


def run_align_corpus(args, downloaded_acoustic_models=None, download_dictionaries=None):
    if downloaded_acoustic_models is None:
        downloaded_acoustic_models = get_available_acoustic_languages()
    if download_dictionaries is None:
        download_dictionaries = get_available_dict_languages()
    try:
        args.speaker_characters = int(args.speaker_characters)
    except ValueError:
        pass
    args.output_directory = args.output_directory.rstrip('/').rstrip('\\')
    args.corpus_directory = args.corpus_directory.rstrip('/').rstrip('\\')

    validate_args(args, downloaded_acoustic_models, download_dictionaries)
    align_corpus(args)


if __name__ == '__main__':  # pragma: no cover
    mp.freeze_support()
    from montreal_forced_aligner.command_line.mfa import align_parser, fix_path, unfix_path, acoustic_languages, dict_languages

    align_args = align_parser.parse_args()
    fix_path()
    run_align_corpus(align_args, acoustic_languages, dict_languages)
    unfix_path()
