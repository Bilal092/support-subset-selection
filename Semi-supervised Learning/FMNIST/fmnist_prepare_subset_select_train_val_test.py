from __future__ import print_function
import torch.utils.data as data
from PIL import Image
import os
import os.path
import gzip
import numpy as np
import torch
import codecs
from utils import download_url, makedir_exist_ok

# Dataset for Fashion-MNIST
class F_MNIST(data.Dataset):
    urls = [
        'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-images-idx3-ubyte.gz',
        'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/train-labels-idx1-ubyte.gz',
        'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/t10k-images-idx3-ubyte.gz',
        'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/t10k-labels-idx1-ubyte.gz',
    ]
    raw_folder = 'f_raw'
    processed_folder = 'f_processed'
    training_file = 'training.pt'
    test_file = 'test.pt'

    training_file = 'training.pt'
    test_file = 'test.pt'
    classes = ["0 - T-shirt/top", "1 - Trouser", "2 - Pullover", "3 - Dress", "4 - Coat", "5 - Sandal", 
               "6 - Shirt", "7 - Sneaker", "8 - Bag", "9 - Ankle boot"]

    def __init__(self, root, split='train', train_ratio=0.8, trust_prop=0.5, transform=None, target_transform=None, download=False):
        self.root = os.path.expanduser(root)
        self.transform = transform
        self.target_transform = target_transform
        self.split = split  # training set or test set
        self.train_ratio = train_ratio
        self.trust_prop = trust_prop

        if download:
            self.download()

        if not self._check_exists():
            raise RuntimeError('Dataset not found.' +
                               ' You can use download=True to download it')

        if self.split == 'test':
            data_file = self.test_file
        else:
            data_file = self.training_file
        self.data, self.targets = torch.load(
            os.path.join(self.processed_folder, data_file))
        self.targets = self.targets.numpy()
        self.num_class = len(np.unique(self.targets))
        self.num_data = len(self.data)

        # weights and clean-noisy indicator intialization
        self.weights = np.ones(len(self.data))
        self.clean_noisy_indicators = np.ones(len(self.data))

        if self.split != 'test':
            num_data = len(self.data)
            train_num = int(num_data * train_ratio)
            trust_num = int(self.trust_prop*train_num)
            if self.split == 'train':
                self.data = self.data[:train_num]
                self.targets = self.targets[:train_num]
                self.clean_noisy_indicators = self.clean_noisy_indicators[:train_num]
                self.weights = self.weights[:train_num]
                self.clean_noisy_indicators[:trust_num] = 1.0
                self.clean_noisy_indicators[trust_num:train_num] = 0.0
                self.weights[:trust_num] = 1.0
                self.weights[trust_num:train_num] = 0.0

            if self.split == 'val':
                self.data = self.data[train_num:]
                self.targets = self.targets[train_num:]
                self.clean_noisy_indicators = self.clean_noisy_indicators[train_num:]
                self.weights = self.weights[train_num:]
                self.clean_noisy_indicators[train_num:] = 1.0
                self.weights[train_num:] = 1.0

    def __getitem__(self, index):
        """
        Args:
            index (int): Index

        Returns:
            tuple: (image, target) where target is index of the target class.
        """
        img, target, weight, clean_noisy_indicator = self.data[index], self.targets[
            index], self.weights[index], self.clean_noisy_indicators[index]

        # doing this so that it is consistent with all other datasets
        # to return a PIL Image
        img = Image.fromarray(img.numpy(), mode='L')

        if self.transform is not None:
            img = self.transform(img)

        if self.target_transform is not None:
            target = self.target_transform(target)

        return img, target, weight, clean_noisy_indicator, index

    def __len__(self):
        return len(self.data)

    @property
    def raw_folder(self):
        return os.path.join(self.root, self.__class__.__name__, 'raw')

    @property
    def processed_folder(self):
        return os.path.join(self.root, self.__class__.__name__, 'processed')

    @property
    def class_to_idx(self):
        return {_class: i for i, _class in enumerate(self.classes)}

    def _check_exists(self):
        return os.path.exists(os.path.join(self.processed_folder, self.training_file)) and \
            os.path.exists(os.path.join(self.processed_folder, self.test_file))

    @staticmethod
    def extract_gzip(gzip_path, remove_finished=False):
        print('Extracting {}'.format(gzip_path))
        with open(gzip_path.replace('.gz', ''), 'wb') as out_f, \
                gzip.GzipFile(gzip_path) as zip_f:
            out_f.write(zip_f.read())
        if remove_finished:
            os.unlink(gzip_path)

    def download(self):
        """Download the MNIST data if it doesn't exist in processed_folder already."""

        if self._check_exists():
            return

        makedir_exist_ok(self.raw_folder)
        makedir_exist_ok(self.processed_folder)

        # download files
        for url in self.urls:
            filename = url.rpartition('/')[2]
            file_path = os.path.join(self.raw_folder, filename)
            download_url(url, root=self.raw_folder,
                         filename=filename, md5=None)
            self.extract_gzip(gzip_path=file_path, remove_finished=True)

        # process and save as torch files
        print('Processing...')

        training_set = (
            read_image_file(os.path.join(self.raw_folder, 'train-images-idx3-ubyte')),
            read_label_file(os.path.join(self.raw_folder, 'train-labels-idx1-ubyte'))
            )
        test_set = (
            read_image_file(os.path.join(self.raw_folder, 't10k-images-idx3-ubyte')),
            read_label_file(os.path.join(self.raw_folder, 't10k-labels-idx1-ubyte'))
        )
        with open(os.path.join(self.processed_folder, self.training_file), 'wb') as f:
            torch.save(training_set, f)
        with open(os.path.join(self.processed_folder, self.test_file), 'wb') as f:
            torch.save(test_set, f)

        print('Done!')

    def __repr__(self):
        fmt_str = 'Dataset ' + self.__class__.__name__ + '\n'
        fmt_str += '    Number of datapoints: {}\n'.format(self.__len__())
        tmp = self.split
        fmt_str += '    Split: {}\n'.format(tmp)
        fmt_str += '    Root Location: {}\n'.format(self.root)
        tmp = '    Transforms (if any): '
        fmt_str += '{0}{1}\n'.format(
            tmp, self.transform.__repr__().replace('\n', '\n' + ' ' * len(tmp)))
        tmp = '    Target Transforms (if any): '
        fmt_str += '{0}{1}'.format(
            tmp, self.target_transform.__repr__().replace('\n', '\n' + ' ' * len(tmp)))
        return fmt_str

    def update_weights(self, weight, index_list):
        self.weights[index_list] = weight

    def get_noisy_labels_with_indices(self):
        noisy_labels = self.targets[self.clean_noisy_indicators == 0.0]
        noisy_indices = list(np.argwhere(
            self.clean_noisy_indicators == 0.0).squeeze())
        return noisy_labels, noisy_indices

    def update_corrupted_label(self, noise_label, noisy_indices):
        self.targets[noisy_indices] = noise_label

    def get_clean_labels_with_indices(self):
        clean_labels = self.targets[self.clean_noisy_indicators == 1.0]
        clean_indices = list(np.argwhere(
            self.clean_noisy_indicators == 1.0).squeeze())
        return clean_labels, clean_indices

    # def update_corrupted_label(self, noise_label):
    #     self.targets[:] = noise_label[:]

    # def update_corrupted_softlabel(self, noise_label):
    #     self.softlabel[:] = noise_label[:]

    # def modify_selected_data(self, modified_data, indices):
    #     self.data[indices] = modified_data

    # def modify_selected_label(self, modified_label, indices):
    #     temp = np.array(self.targets)
    #     temp[indices] = modified_label
    #     self.targets = list(temp)

    # def modify_selected_softlabel(self, modified_softlabel, indices):
    #     self.softlabel[indices] = modified_softlabel

    # def update_selected_data(self, selected_indices):
    #     self.data = self.data[selected_indices]

    #     self.targets = np.array(self.targets)
    #     self.targets = self.targets[selected_indices]
    #     self.targets = self.targets.tolist()

    # def ignore_noise_data(self, noisy_data_indices):
    #     total = len(self.data)
    #     remain = list(set(range(total)) - set(noisy_data_indices))
    #     remain = np.array(remain)

    #     self.data = self.data[remain]
    #     self.targets = np.array(self.targets)
    #     self.targets = self.targets[remain]
    #     self.targets = self.targets.tolist()
    #     self.softlabel = self.softlabel[remain]

    # def get_data_labels(self):
    #     return self.targets

    # def get_data_softlabel(self):
    #     return self.softlabel


def get_int(b):
    return int(codecs.encode(b, 'hex'), 16)


def read_label_file(path):
    with open(path, 'rb') as f:
        data = f.read()
        assert get_int(data[:4]) == 2049
        length = get_int(data[4:8])
        parsed = np.frombuffer(data, dtype=np.uint8, offset=8)
        return torch.from_numpy(parsed).view(length).long()


def read_image_file(path):
    with open(path, 'rb') as f:
        data = f.read()
        assert get_int(data[:4]) == 2051
        length = get_int(data[4:8])
        num_rows = get_int(data[8:12])
        num_cols = get_int(data[12:16])
        parsed = np.frombuffer(data, dtype=np.uint8, offset=16)
        return torch.from_numpy(parsed).view(length, num_rows, num_cols)
