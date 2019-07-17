

import unittest
from unittest.mock import Mock

import os
import shutil
import filecmp
import torch
import soundfile
import pydub
import array

from idiaptts.src.model_trainers.ModelTrainer import ModelTrainer
from idiaptts.src.data_preparation.questions.QuestionLabelGen import QuestionLabelGen
from idiaptts.src.data_preparation.world.WorldFeatLabelGen import WorldFeatLabelGen
from idiaptts.src.data_preparation.PyTorchLabelGensDataset import PyTorchLabelGensDataset as LabelGensDataset
from idiaptts.src.neural_networks.pytorch.utils import equal_checkpoint
from idiaptts.misc.utils import makedirs_safe


class TestModelTrainer(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        hparams = cls._get_hparams(cls())
        makedirs_safe(hparams.out_dir)  # Create class name directory.
        # Load test data
        cls.id_list = cls._get_id_list()

    @classmethod
    def tearDownClass(cls):
        hparams = cls._get_hparams(cls())
        os.rmdir(hparams.out_dir)  # Remove class name directory, should be empty.

    def _get_hparams(self):
        hparams = ModelTrainer.create_hparams()
        # General parameters
        hparams.num_questions = 425
        hparams.epochs = 0
        hparams.test_set_perc = 0.05
        hparams.val_set_perc = 0.05
        hparams.seed = None  # Remove the default seed.
        hparams.out_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), type(self).__name__)
        hparams.num_coded_sps = 30

        # Training parameters.
        hparams.epochs = 0
        hparams.model_name = "test_model.nn"

        return hparams

    @staticmethod
    def _get_id_list():
        with open(os.path.join("integration", "fixtures", "database", "file_id_list.txt")) as f:
            id_list = f.readlines()
        # Trim entries in-place.
        id_list[:] = [s.strip(' \t\n\r') for s in id_list]
        return id_list

    def _get_trainer(self, hparams):
        dir_world_features = "integration/fixtures/WORLD"
        dir_question_labels = "integration/fixtures/questions"

        trainer = ModelTrainer(self.id_list, hparams)

        # Create datasets to work on.
        trainer.InputGen = QuestionLabelGen(dir_question_labels, hparams.num_questions)
        trainer.InputGen.get_normalisation_params(dir_question_labels)

        trainer.OutputGen = WorldFeatLabelGen(dir_world_features, num_coded_sps=hparams.num_coded_sps, add_deltas=True)
        trainer.OutputGen.get_normalisation_params(dir_world_features)

        trainer.dataset_train = LabelGensDataset(trainer.id_list_train, trainer.InputGen, trainer.OutputGen, hparams)
        trainer.dataset_val = LabelGensDataset(trainer.id_list_val, trainer.InputGen, trainer.OutputGen, hparams)

        trainer.loss_function = torch.nn.MSELoss(reduction='none')

        return trainer

    def test_init_hparams_none(self):
        with self.assertRaises(AssertionError):
            self._get_trainer(None)

    def test_init_no_model_type_and_saved_model(self):
        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_init_no_model_type_and_saved_model")  # Add function name to path.
        trainer = self._get_trainer(hparams)
        # Check fail when neither model_type is given nor a model exists with model_name.
        with self.assertRaises(FileNotFoundError):
            trainer.init(hparams)
        shutil.rmtree(hparams.out_dir)

    def test_init_test55_val55_set_split(self):
        hparams = self._get_hparams()

        with self.assertRaises(AssertionError):
            hparams.val_set_perc = .55
            hparams.test_set_perc = .55
            self._get_trainer(hparams)

    def test_init_test0_val0_set_split(self):
        hparams = self._get_hparams()
        hparams.val_set_perc = 0.0
        hparams.test_set_perc = 0.0
        trainer = self._get_trainer(hparams)

        self.assertEqual(len(self.id_list), len(trainer.id_list_train))
        self.assertIsNone(trainer.id_list_val)
        self.assertIsNone(trainer.id_list_test)

    def test_init_test33_val0_set_split(self):
        hparams = self._get_hparams()
        hparams.val_set_perc = 0.0
        hparams.test_set_perc = 0.33
        trainer = self._get_trainer(hparams)

        self.assertIsNone(trainer.id_list_val)

        expected_length = max(1, int(len(self.id_list) * hparams.test_set_perc))
        self.assertEqual(expected_length, len(trainer.id_list_test))
        self.assertEqual(len(self.id_list) - expected_length, len(trainer.id_list_train))

    def test_init_test0_val66_set_split(self):
        hparams = self._get_hparams()
        hparams.val_set_perc = 0.66
        hparams.test_set_perc = 0.0
        trainer = self._get_trainer(hparams)

        self.assertIsNone(trainer.id_list_test)

        expected_length = max(1, int(len(self.id_list) * hparams.val_set_perc))
        self.assertEqual(expected_length, len(trainer.id_list_val))
        self.assertEqual(len(self.id_list) - expected_length, len(trainer.id_list_train))

    def test_init_test20_val40_set_split(self):
        hparams = self._get_hparams()
        hparams.val_set_perc = 0.4
        hparams.test_set_perc = 0.2
        trainer = self._get_trainer(hparams)

        # Check length of id lists.
        expected_val_length = max(1, int(len(self.id_list) * hparams.val_set_perc))
        expected_test_length = max(1, int(len(self.id_list) * hparams.test_set_perc))
        self.assertEqual(expected_test_length, len(trainer.id_list_test))
        self.assertEqual(expected_val_length, len(trainer.id_list_val))
        self.assertEqual(len(self.id_list) - expected_test_length - expected_val_length, len(trainer.id_list_train))
        self.assertEqual(len(self.id_list), len(trainer.id_list_train) + len(trainer.id_list_test) + len(trainer.id_list_val))

        # Check that all lists are disjoint.
        test_in_train = list(set(trainer.id_list_train).intersection(trainer.id_list_test))
        self.assertEqual(0, len(test_in_train), msg="Found test id(s) in train set: {}".format(test_in_train))
        val_in_train = list(set(trainer.id_list_train).intersection(trainer.id_list_val))
        self.assertEqual(0, len(val_in_train), msg="Found validation id(s) in train set: {}".format(val_in_train))
        val_in_test = list(set(trainer.id_list_val).intersection(trainer.id_list_test))
        self.assertEqual(0, len(val_in_test), msg="Found validation id(s) in test set: {}".format(val_in_test))

    def test_init_e0_create(self):
        # Try epochs=0, loading will fail because no model exists, create a new one.
        hparams = self._get_hparams()
        hparams.epochs = 0
        hparams.out_dir = os.path.join(hparams.out_dir, "test_init_e0_create")  # Add function name to path.
        hparams.use_gpu = True
        hparams.model_type = "RNNDYN-1_RELU_32-1_FC_97"
        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        # Check if model is loaded and saved, but no checkpoint exists.
        self.assertIsNotNone(trainer.model_handler.model)
        self.assertTrue(os.path.isfile(os.path.join(hparams.out_dir, hparams.networks_dir, hparams.model_name)))
        self.assertEqual(0, len([name for name in os.listdir(os.path.join(hparams.out_dir,
                                                                          hparams.networks_dir,
                                                                          hparams.checkpoints_dir)) if os.path.isfile(name)]))

        shutil.rmtree(hparams.out_dir)

    def test_init_e0_load(self):
        # Try epochs=0, loading existing model.
        hparams = self._get_hparams()
        hparams.epochs = 0
        hparams.out_dir = os.path.join(hparams.out_dir, "test_init_e0_load")  # Add function name to path.
        hparams.model_type = None
        trainer = self._get_trainer(hparams)
        target_dir = os.path.join(hparams.out_dir, hparams.networks_dir)
        makedirs_safe(target_dir)
        shutil.copyfile(os.path.join("integration", "fixtures", "test_model_97.nn"), os.path.join(target_dir, hparams.model_name))
        trainer.init(hparams)
        self.assertIsNotNone(trainer.model_handler.model)

        shutil.rmtree(hparams.out_dir)

    def test_init_e3_create(self):
        # Try epochs=3, creating a new model.
        hparams = self._get_hparams()
        hparams.epochs = 3
        hparams.out_dir = os.path.join(hparams.out_dir, "test_init_e3_create")  # Add function name to path.
        hparams.model_type = "RNNDYN-1_RELU_32-1_FC_97"
        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        self.assertIsNotNone(trainer.model_handler.model)

        shutil.rmtree(hparams.out_dir)

    def test_init_e3_load(self):
        # Try epochs=3, loading existing model.
        hparams = self._get_hparams()
        hparams.epochs = 3
        hparams.out_dir = os.path.join(hparams.out_dir, "test_init_e3_load")  # Add function name to path.
        hparams.model_type = None
        target_dir = os.path.join(hparams.out_dir, hparams.networks_dir)
        makedirs_safe(target_dir)
        shutil.copyfile(os.path.join("integration", "fixtures", "test_model_97.nn"), os.path.join(target_dir, hparams.model_name))
        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        self.assertIsNotNone(trainer.model_handler.model)

        shutil.rmtree(hparams.out_dir)

    def test_train_e0(self):
        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_train_e0")  # Add function name to path.
        trainer = self._get_trainer(hparams)

        hparams.model_type = "RNNDYN-1_RELU_32-1_FC_97"
        trainer.init(hparams)
        all_loss, all_loss_train, _ = trainer.train(hparams)
        # Check if no training happened.
        self.assertEqual(0, len(all_loss))
        self.assertEqual(0, len(all_loss_train))

        shutil.rmtree(hparams.out_dir)

    def test_train_e3(self):
        for seed in [345]: # itertools.count(0):
            hparams = self._get_hparams()
            hparams.out_dir = os.path.join(hparams.out_dir, "test_train_e3")  # Add function name to path.
            hparams.seed = seed
            trainer = self._get_trainer(hparams)

            hparams.model_type = "RNNDYN-1_RELU_32-1_FC_97"
            hparams.epochs = 4
            hparams.batch_size_train = 2
            hparams.batch_size_val = hparams.batch_size_train
            hparams.epochs_per_checkpoint = 2
            trainer.init(hparams)
            hparams.optimiser_args["lr"] = 0.01
            hparams.scheduler_type = "Plateau"
            hparams.use_best_as_final_model = False
            all_loss, all_loss_train, _ = trainer.train(hparams)

            if all_loss[-1] > min(all_loss) and all_loss_train[-1] < all_loss_train[1 if hparams.start_with_test else 0]:
                break

        # print(all_loss)
        # print(seed)

        # Training loss decreases?
        self.assertLess(all_loss_train[-1],
                        all_loss_train[1 if hparams.start_with_test else 0],
                        msg="Training loss did not decrease over {} epochs: {}".format(hparams.epochs, all_loss_train))

        # Expected number of checkpoints saved?
        checkpoint_dir = os.path.join(hparams.out_dir, hparams.networks_dir, hparams.checkpoints_dir)
        self.assertEqual(int(hparams.epochs / hparams.epochs_per_checkpoint) + 1,
                         len([name for name in os.listdir(checkpoint_dir) if os.path.isfile(os.path.join(checkpoint_dir, name))]))

        # Final model saved?
        saved_model_path = os.path.join(hparams.out_dir, hparams.networks_dir, hparams.model_name)
        self.assertTrue(os.path.isfile(saved_model_path))

        # Final model is last model?
        self.assertTrue(filecmp.cmp(saved_model_path, os.path.join(checkpoint_dir, hparams.model_name + "-e{}-{}".format(hparams.epochs, trainer.loss_function)), False),
                        msg="Saved model is not the same as final checkpoint.")
        # Final model is not best model.
        self.assertFalse(filecmp.cmp(saved_model_path, os.path.join(checkpoint_dir, hparams.model_name + "-best"), False),
                         msg="Saved model is the same as best model which should not be the same as the last epoch.")

        shutil.rmtree(hparams.out_dir)

    def test_train_e3_save_best(self):
        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_train_e3_save_best")  # Add function name to path.
        hparams.seed = 1234
        trainer = self._get_trainer(hparams)

        hparams.model_type = "RNNDYN-1_RELU_32-1_FC_97"
        hparams.epochs = 4
        hparams.batch_size_train = 2
        hparams.batch_size_val = hparams.batch_size_train
        hparams.epochs_per_checkpoint = 2
        trainer.init(hparams)
        hparams.optimiser_args["lr"] = 0.001
        hparams.scheduler_type = "Plateau"
        hparams.use_best_as_final_model = True
        _, all_loss_train, _ = trainer.train(hparams)

        # Final model is best model?
        checkpoint_dir = os.path.join(hparams.out_dir, hparams.networks_dir, hparams.checkpoints_dir)
        saved_model_path = os.path.join(hparams.out_dir, hparams.networks_dir, hparams.model_name)
        self.assertTrue(equal_checkpoint(saved_model_path, os.path.join(checkpoint_dir, hparams.model_name + "-best")),
                        msg="Saved model is not the same as best model.")

        shutil.rmtree(hparams.out_dir)

    def test_train_no_best_model(self):
        # Load a model, and use a seed so that test loss goes up. Check if no best model is there.
        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_train_no_best_model")  # Add function name to path
        hparams.model_name = "test_model_97.nn"
        hparams.model_dir = os.path.join("integration", "fixtures")
        hparams.seed = 1234
        hparams.batch_size_train = 2
        hparams.batch_size_val = hparams.batch_size_train
        hparams.epochs = 1
        hparams.use_best_as_final_model = True
        hparams.optimiser_args["lr"] = 0.001
        hparams.scheduler_type = "Plateau"

        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        with unittest.mock.patch.object(trainer.logger, "warning") as mock_logger:
            trainer.train(hparams)
            mock_logger.assert_called_with("No best model exists yet. Continue with the current one.")

        shutil.rmtree(hparams.out_dir)

    def test_synth_wav(self):
        num_test_files = 2

        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_synth_wav")  # Add function name to path
        hparams.model_name = "test_model_97.nn"
        hparams.model_dir = os.path.join("integration", "fixtures")
        hparams.synth_fs = 16000
        hparams.frame_size_ms = 5
        hparams.synth_ext = "wav"

        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        hparams.synth_dir = hparams.out_dir
        trainer.synth(hparams, self.id_list[:num_test_files])

        found_files = list([name for name in os.listdir(hparams.synth_dir)
                            if os.path.isfile(os.path.join(hparams.synth_dir, name))
                            and name.endswith("_WORLD." + hparams.synth_ext)])
        # Check number of created files.
        self.assertEqual(len(self.id_list[:num_test_files]), len(found_files),
                         msg="Number of {} files in synth_dir directory does not match.".format(hparams.synth_ext))

        # Check readability and length of one created file.
        raw, fs = soundfile.read(os.path.join(hparams.synth_dir, found_files[0]))
        self.assertEqual(hparams.synth_fs, fs, msg="Desired sampling frequency of output doesn't match.")
        labels = trainer.OutputGen[[id_name for id_name in self.id_list[:num_test_files] if id_name in found_files[0]][0]]
        expected_length = len(raw) / hparams.synth_fs / hparams.frame_size_ms * 1000
        self.assertTrue(abs(expected_length - len(labels)) < 10,
                        msg="Saved raw audio file length does not roughly match length of labels.")

        shutil.rmtree(hparams.out_dir)

    def test_synth_mp3(self):
        num_test_files = 2

        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_synth_mp3")  # Add function name to path
        hparams.model_name = "test_model_97.nn"
        hparams.model_dir = os.path.join("integration", "fixtures")
        hparams.synth_fs = 16000
        hparams.frame_size_ms = 5
        hparams.synth_ext = "mp3"

        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        hparams.synth_dir = hparams.out_dir
        trainer.synth(hparams, self.id_list[:num_test_files])

        found_files = list([name for name in os.listdir(hparams.synth_dir)
                            if os.path.isfile(os.path.join(hparams.synth_dir, name))
                            and name.endswith("_WORLD." + hparams.synth_ext)])
        found_files_wav = list([name for name in os.listdir(hparams.synth_dir)
                                if os.path.isfile(os.path.join(hparams.synth_dir, name))
                                and name.endswith("_WORLD.wav")])
        # Check number of created files.
        self.assertEqual(len(self.id_list[:num_test_files]), len(found_files),
                         msg="Number of {} files in synth_dir directory does not match.".format(hparams.synth_ext))
        self.assertEqual(0, len(found_files_wav), msg="Did not expect any wav files in the synth_dir directory.")

        # Check readability and length of one created file, requires some steps because it is mp3.
        sound = pydub.AudioSegment.from_file(os.path.join(hparams.synth_dir, found_files[0]))
        bit_depth = sound.split_to_mono()[0].sample_width * 8
        array_type = pydub.utils.get_array_type(bit_depth)
        fs = bit_depth * 1000
        raw = array.array(array_type, sound.split_to_mono()[0]._data)

        self.assertEqual(hparams.synth_fs, fs, msg="Desired sampling frequency of output doesn't match.")
        labels = trainer.OutputGen[[id_name for id_name in self.id_list[:num_test_files] if id_name in found_files[0]][0]]
        expected_length = len(raw) / hparams.synth_fs / hparams.frame_size_ms * 1000
        self.assertTrue(abs(expected_length - len(labels)) < 10,
                        msg="Saved raw audio file length does not roughly match length of labels.")

        shutil.rmtree(hparams.out_dir)

    def test_gen_figure(self):
        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_gen_figure")  # Add function name to path
        hparams.model_name = "test_model_97.nn"
        hparams.model_dir = os.path.join("integration", "fixtures")

        trainer = self._get_trainer(hparams)
        trainer.init(hparams)

        with self.assertRaises(NotImplementedError):
            trainer.gen_figure(hparams, self.id_list)

        shutil.rmtree(hparams.out_dir)

    def test_synth_ref(self):
        num_test_files = 2

        hparams = self._get_hparams()
        hparams.out_dir = os.path.join(hparams.out_dir, "test_synth_ref")  # Add function name to path
        hparams.model_name = "test_model_97.nn"
        hparams.model_dir = os.path.join("integration", "fixtures")
        hparams.synth_fs = 16000
        hparams.frame_size_ms = 5
        hparams.synth_ext = "mp3"

        trainer = self._get_trainer(hparams)
        trainer.init(hparams)
        hparams.synth_dir = hparams.out_dir
        trainer.synth_ref(hparams, self.id_list[:num_test_files])

        found_files = list([name for name in os.listdir(hparams.synth_dir)
                            if os.path.isfile(os.path.join(hparams.synth_dir, name))
                            and name.endswith("_ref{}sp_WORLD.{}".format(hparams.num_coded_sps, hparams.synth_ext))])
        found_files_wav = list([name for name in os.listdir(hparams.synth_dir)
                                if os.path.isfile(os.path.join(hparams.synth_dir, name))
                                and name.endswith("_ref{}sp_WORLD.wav".format(hparams.num_coded_sps))])
        # Check number of created files.
        self.assertEqual(len(self.id_list[:num_test_files]), len(found_files),
                         msg="Number of {} files in synth_dir directory does not match.".format(hparams.synth_ext))
        self.assertEqual(0, len(found_files_wav), msg="Did not expect any wav files in the synth_dir directory.")

        # Check readability and length of one created file, requires some steps because it is mp3.
        sound = pydub.AudioSegment.from_file(os.path.join(hparams.synth_dir, found_files[0]))
        bit_depth = sound.split_to_mono()[0].sample_width * 8
        array_type = pydub.utils.get_array_type(bit_depth)
        fs = bit_depth * 1000
        raw = array.array(array_type, sound.split_to_mono()[0]._data)

        self.assertEqual(hparams.synth_fs, fs, msg="Desired sampling frequency of output doesn't match.")
        labels = trainer.OutputGen[[id_name for id_name in self.id_list[:num_test_files] if id_name in found_files[0]][0]]
        expected_length = len(raw) / hparams.synth_fs / hparams.frame_size_ms * 1000
        self.assertTrue(abs(expected_length - len(labels)) < 10,
                        msg="Saved raw audio file length does not roughly match length of labels.")

        shutil.rmtree(hparams.out_dir)


# TODO: Test with GRU
# TODO: Multispeaker tests.
# TODO: Everything with batch_first=True
