# encoding: utf-8

import math
import random
import torchvision.transforms as T
import torch


def build_transforms(size):
    normalize_transform = T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    transforms = T.Compose([
        T.Resize(size),
        #T.Pad(10),
        #T.RandomCrop([256, 128]),
        T.ToTensor(),
        normalize_transform,
        #RandomErasing(probability=0.5, mean=[0.485, 0.456, 0.406])
    ])
    return transforms

def build_transforms_shape(size, mode = 'train'):
    if mode == 'train':
        transforms = T.Compose([
            T.Resize(size),
            T.Pad(10),
            T.RandomCrop(size)
        ])
    else:
        transforms = T.Compose([
            T.Resize(size)
        ])
    return transforms

def build_transformers_value(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225], p = 0.5, mode = 'train'):
    if mode == 'train':
        transforms = T.Compose([
            T.Normalize(mean=mean, std=std),
            RandomErasing(probability=p, mean=mean)
        ])
    else:
        transforms = T.Compose([
            T.Normalize(mean=mean, std=std)
        ])
    return transforms

def build_transforms_mask():
    transforms = T.Compose([
        T.Resize([256, 128]),
        #T.Pad(10),
        #T.RandomCrop([256, 128]),
        #ChangeZeroTo(0.1)
    ])
    return transforms

class ChangeZeroTo(object):
    '''
    for a tensor, change all zero elements to x
    and others do not change
    '''
    def __init__(self, x):
        self.x = x

    def __call__(self, t_input):
        t_flag = (t_input == 0).int()
        return t_input + t_flag * self.x

class RandomErasing(object):
    """ Randomly selects a rectangle region in an image and erases its pixels.
        'Random Erasing Data Augmentation' by Zhong et al.
        See https://arxiv.org/pdf/1708.04896.pdf
    Args:
         probability: The probability that the Random Erasing operation will be performed.
         sl: Minimum proportion of erased area against input image.
         sh: Maximum proportion of erased area against input image.
         r1: Minimum aspect ratio of erased area.
         mean: Erasing value.
    """

    def __init__(self, probability=0.5, sl=0.02, sh=0.4, r1=0.3, mean=(0.4914, 0.4822, 0.4465)):
        self.probability = probability
        self.mean = mean
        self.sl = sl
        self.sh = sh
        self.r1 = r1

    def __call__(self, img):

        if random.uniform(0, 1) >= self.probability:
            return img

        for attempt in range(100):
            area = img.size()[1] * img.size()[2]

            target_area = random.uniform(self.sl, self.sh) * area
            aspect_ratio = random.uniform(self.r1, 1 / self.r1)

            h = int(round(math.sqrt(target_area * aspect_ratio)))
            w = int(round(math.sqrt(target_area / aspect_ratio)))

            if w < img.size()[2] and h < img.size()[1]:
                x1 = random.randint(0, img.size()[1] - h)
                y1 = random.randint(0, img.size()[2] - w)
                if img.size()[0] == 3:
                    img[0, x1:x1 + h, y1:y1 + w] = self.mean[0]
                    img[1, x1:x1 + h, y1:y1 + w] = self.mean[1]
                    img[2, x1:x1 + h, y1:y1 + w] = self.mean[2]
                else:
                    img[0, x1:x1 + h, y1:y1 + w] = self.mean[0]
                return img

        return img
