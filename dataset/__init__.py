import random

import torch
import os.path as osp
from PIL import Image
from torch.utils.data import Dataset
from dataset.dataset_duke import Duke
from dataset.dataset_market import Market
from dataset.dataset_msmt import MSMT17
from dataset.dataset_ltcc import LTCC
import numpy as np
import dataset.method_reading as m
import logging

DATASET_MAP = {
    'market': Market,
    'duke': Duke,
    'msmt17': MSMT17,
    'ltcc': LTCC
}
__factory_reading_m = {
    'get_img': m.GetImg,
    'get_img_sem': m.GetImgSem
}

def initial_m_reading(method_name, **kwargs):
    '''
    initial reading data method
    :param method_name: method name in __factory_reading_m
    :param kwargs:
    :return:
    '''
    if method_name not in __factory_reading_m.keys():
        logging.error(f'Method [{method_name}] is not supported')
        raise Exception
    return __factory_reading_m[method_name](**kwargs)


class DatasetManager(object):
    def __init__(self, dataset_name, dataset_dir):
        self.dataset_name = dataset_name
        if not dataset_name in DATASET_MAP.keys():
            logging.error('dataset_name no exist. support:' + ','.join(DATASET_MAP.keys()))
            return
        self.dataset = DATASET_MAP.get(dataset_name)(dataset_dir)

    def get_train_pid_num(self):
        return self.dataset.num_train_pids

    def get_dataset_list(self, mode):
        return getattr(self.dataset, mode)

    def get_dataset_image(self, mode, m_reading):
        if not hasattr(self.dataset, mode):
            logging.error('can not find mode:' + mode + ' in dataset:' + self.dataset_name)
            return None
        datalist = getattr(self.dataset, mode)
        return DatasetImage(datalist, m_reading)


class DatasetImage(Dataset):
    """Image Person ReID Dataset"""

    def __init__(self, dataset, m_reading):
        self.dataset = dataset
        self.m_reading = m_reading

    def __len__(self):
        return len(self.dataset)

    def __getitem__(self, index):
        """
        :param index:
        :param m_reading: method to read the data, generate dict
        :return:
        """
        return self.m_reading(self.dataset[index])

