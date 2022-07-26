import argparse
import torch
import os
import logging
import datetime
from dataset import DatasetManager, initial_m_reading
from model import ModelManager
from torch.utils.data import DataLoader
import yaml
import numpy as np
import random
from torch.utils.tensorboard import SummaryWriter
from dataset.sampler import RandomIdentitySampler, RandomIdentitySamplerCC
import tools


def set_seed(seed):
    torch.manual_seed(seed)
    torch.cuda.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    np.random.seed(seed)
    random.seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = True


# set cuda visible devices, and return the first gpu device
def set_gpus_env(gpu_ids):
    os.environ['CUDA_VISIBLE_DEVICES'] = ','.join([str(id) for id in gpu_ids])
    if not torch.cuda.is_available():
        logging.warning('Cuda is not available using cpu')
        return torch.device('cpu')
    gpus_count = torch.cuda.device_count()
    for gpu_id in gpu_ids:
        if gpu_ids.index(gpu_id) >= gpus_count:
            logging.warning('gpu id:{0} exceeds the limit , which only have {1} gpus'.format(gpu_id, gpus_count))
            gpu_ids.remove(gpu_id)
        logging.info(
            'using gpu: id is ' + str(gpu_id) + ' name is ' + torch.cuda.get_device_name(gpu_ids.index(gpu_id)))
    if len(gpu_ids) == 0:
        gpu_ids.append(0)
        logging.warning('all the config gpus can not be used, use gpu:0')
    return torch.device('cuda:0')


def main(config, writer_tensorboardX):
    set_seed(config.get('seed', 1234))
    device = set_gpus_env(config.get('gpu', [0]))
    mode = config.get('mode', 'train')
    model_config = config.get('model-manager', dict())

    # Statistical parameters and Flops
    if mode == 'statistics':
        model = ModelManager(model_config, device)
        if not 'inputs_shape' in model_config.keys():
            logging.error('Input the inputs shape')
            return
        input_shape_l = model_config.get('inputs_shape')
        model.check_model_params(input_shape_l)
        return

    # vis config
    cfg_vis = config.get('vis_params', dict())
    vis_bool = cfg_vis.get('vis', False)  # draw feature distribution
    vis_interval = cfg_vis.get('vis_interval', 20)  # interval of drawing feature distribution
    eval_interval = config.get('eval_interval', 20)

    dataset_config = config.get('dataset', dict())
    log_dataset_config(dataset_config)
    dataset_manager = DatasetManager(dataset_config.get('dataset_name', ''), dataset_config.get('dataset_path', ''))

    model = ModelManager(model_config, device, class_num=dataset_manager.get_train_pid_num(),
                         writer=writer_tensorboardX)
    dataset_type = dataset_config.get('type', 'image')
    get_dataset = dataset_manager.get_dataset_image  # support image reading for now
    # get reading method
    m_reading_train_cfg = dataset_config.get('reading_method_train')
    m_reading_test_cfg = dataset_config.get('reading_method_test')
    m_reading_train = initial_m_reading(m_reading_train_cfg.get('name'), **m_reading_train_cfg)
    m_reading_test = initial_m_reading(m_reading_test_cfg.get('name'), **m_reading_test_cfg)
    if 'train' == mode:
        logging.info("loading train data")
        batch_size_train = dataset_config.get('batch_size_train', 16)
        num_instance = dataset_config.get('num_instance', 4)  # number of person with same id
        num_per_clothes = dataset_config.get('num_per_clothes', 2)
        dataset_train = get_dataset('train', m_reading_train)
        data_sampler = RandomIdentitySamplerCC(dataset_manager.get_dataset_list('train'),
                                             batch_size_train,
                                             num_instance,
                                             num_per_clothes)
        loader_train_source = DataLoader(
            dataset_train,
            batch_size=batch_size_train,
            num_workers=dataset_config.get('num_workers', 8),
            sampler=data_sampler
        )
        logging.info("load train data finish")
        logging.info("loading test data")
        loader_gallery_source = DataLoader(
            get_dataset('test', m_reading_test),
            batch_size=dataset_config.get('batch_size_test', 16),
            num_workers=dataset_config.get('num_workers', 8),
            drop_last=False,
            shuffle=False
        )
        loader_query_same = DataLoader(
            get_dataset('query', m_reading_test),
            batch_size=dataset_config.get('batch_size_test', 16),
            num_workers=dataset_config.get('num_workers', 8),
            drop_last=False,
            shuffle=False
        )
        visHm = config.get('visHm', False)
        if visHm:
            loader_train_sample = DataLoader(
                get_dataset('train_sample', m_reading_test),
                batch_size=dataset_config.get('batch_size_test', 16),
                num_workers=dataset_config.get('num_workers', 8),
                drop_last=False,
                shuffle=False
            )
        logging.info("load test data finish")
        logging.info("prepare to train from epoch[{0}] to epoch[{1}]".format(model.trained_epoches,
                                                                             model_config.get('epoch', 64)))
        for i in range(model.trained_epoches + 1, model_config.get('epoch', 64) + 1):
            is_vis = (i % vis_interval == 0 or i == model_config.get('epoch', 64))  # each vis_interval or last epoch
            is_vis = is_vis and vis_bool
            model.train(loader_train_source, i, is_vis)
            if (i % eval_interval == 0) or i == model_config.get('epoch', 64):
                if visHm:
                    model.visHeatMap(loader_train_sample, epoch = i)
                model.test(loader_query_same, loader_gallery_source, epoch=i, is_vis=is_vis,
                           sample_method=cfg_vis.get('vis_img_func', 'random'),
                           sample_num=cfg_vis.get('vis_img_num', '100'))
                
    elif 'test' == mode:
        logging.info("loading test data")
        loader_gallery_source = DataLoader(
            get_dataset('test', m_reading_test),
            batch_size=dataset_config.get('batch_size_test', 16),
            num_workers=dataset_config.get('num_workers', 8),
            drop_last=False,
            shuffle=False
        )
        loader_query_same = DataLoader(
            get_dataset('query', m_reading_test),
            batch_size=dataset_config.get('batch_size_test', 16),
            num_workers=dataset_config.get('num_workers', 8),
            drop_last=False,
            shuffle=False
        )
        logging.info("load test data finish")
        model.test(loader_query_same, loader_gallery_source, is_vis=vis_bool,
                   sample_method=cfg_vis.get('vis_img_func', 'random'),
                   sample_num=cfg_vis.get('vis_img_num', '100'))
    else:
        logging.error(f'not support mode:{mode}')

    logging.info("finish!")


def init_logging(task_name='', is_save=True):
    # log config
    log_dir_name = ''
    if is_save:
        log_dir_name = str(datetime.datetime.now().year).rjust(4, '0') \
                       + str(datetime.datetime.now().month).rjust(2, '0') \
                       + str(datetime.datetime.now().day).rjust(2, '0') \
                       + str(datetime.datetime.now().hour).rjust(2, '0') \
                       + str(datetime.datetime.now().minute).rjust(2, '0') \
                       + str(datetime.datetime.now().second).rjust(2, '0')
        if task_name != '':
            log_dir_name = f'{task_name}-{log_dir_name}'
        if not os.path.isdir(f'./output/log/{log_dir_name}'):
            os.mkdir(f'./output/log/{log_dir_name}')
        logging.basicConfig(filename=f'./output/log/{log_dir_name}/log.txt',
                            level=logging.INFO,
                            format='###%(levelname)s###[%(asctime)s]%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
        print(f'writing log to ./output/log/{log_dir_name}')
    else:
        logging.basicConfig(filename=f'./log.txt',
                            level=logging.INFO,
                            format='###%(levelname)s###[%(asctime)s]%(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('[%(asctime)s]%(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logging.getLogger().addHandler(console)
    return log_dir_name


def log_dataset_config(dataset_config: dict):
    logging.info('=> DataSet Info:')
    logging.info(f'----dataset:{dataset_config.get("dataset_name")}')
    logging.info(f'----path:{dataset_config.get("dataset_path")}')
    logging.info(f'----img_size:{dataset_config.get("image_size", [256, 128])}')
    logging.info(f'----batch_size_train:{dataset_config.get("batch_size_train", 16)}')
    logging.info(f'----num_instance:{dataset_config.get("num_instance", 4)}')
    logging.info(f'----batch_size_test:{dataset_config.get("batch_size_test", 16)}')
    logging.info(f'----transform method:{dataset_config.get("transform", "None")}')
    logging.info(f'----num_workers:{dataset_config.get("num_workers", 8)}')


def merge_data(data_1, data_2):
    """
    merge data of two nested dict
    :param data_1:
    :param data_2: priority
    :return:
    """
    if isinstance(data_1, dict) and isinstance(data_2, dict):
        new_dict = {}
        d2_keys = list(data_2.keys())
        for d1k in data_1.keys():
            if d1k in d2_keys:
                d2_keys.remove(d1k)
                new_dict[d1k] = merge_data(data_1.get(d1k), data_2.get(d1k))
            else:
                new_dict[d1k] = data_1.get(d1k)
        for d2k in d2_keys:
            new_dict[d2k] = data_2.get(d2k)
        return new_dict
    else:
        if data_2 == None:
            return data_1
        else:
            return data_2


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cfg_base', type=str, default='config/cfg-base.yaml', help='the config file(.yaml)')
    parser.add_argument('--cfg', type=str, default='config/train-market1501.yaml', help='the config file(.yaml)')
    parser.add_argument('--no_log', action='store_true', default=False, help='do not save log file')

    config = parser.parse_args()
    # base config
    cfg_base_path = config.cfg_base
    if not os.path.exists(cfg_base_path):
        logging.error(f'can not find the base config file:{cfg_base_path}')
    with open(cfg_base_path) as f:
        cfg = f.read()
        yaml_cfg_base = yaml.safe_load(cfg)

    # detail config
    cfg_path = config.cfg
    if not os.path.exists(cfg_path):
        logging.error(f'can not find the config file:{cfg_path}')
    with open(cfg_path) as f:
        cfg = f.read()
        yaml_cfg_detail = yaml.safe_load(cfg)

    yaml_cfg = merge_data(yaml_cfg_base, yaml_cfg_detail)
    if not os.path.isdir('./output'):
        os.mkdir('./output')
    if not os.path.isdir('./output/log'):
        os.mkdir('./output/log')

    yaml_str = str(tools.format_dict(yaml_cfg))

    if not config.no_log:
        # initial logging module
        log_dir_name = init_logging(task_name=yaml_cfg.get('task-name', ''))
        # initial tensorboardX
        writer_tensorboardx = SummaryWriter(f'./output/log/{log_dir_name}')
        # for html display convert
        yaml_str_html = yaml_str.replace('\n', '<br>')
        yaml_str_html = yaml_str_html.replace(' ', "&nbsp;")
        writer_tensorboardx.add_text('config', yaml_str_html)
    else:
        init_logging(task_name=yaml_cfg.get('task-name', ''), is_save=False)
        writer_tensorboardx = None

    logging.info('=> Config File:')
    logging.info(yaml_str)

    main(yaml_cfg, writer_tensorboardx)
    if not writer_tensorboardx == None:
        writer_tensorboardx.close()
