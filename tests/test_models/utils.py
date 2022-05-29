# Copyright (c) OpenMMLab. All rights reserved.
import copy
from os.path import dirname, exists, join

import numpy as np
import torch
from mmengine.data import InstanceData

from mmtrack.core import TrackDataSample


def _get_config_directory():
    """Find the predefined video detector or tracker config directory."""
    try:
        # Assume we are running in the source mmtracking repo
        repo_dpath = dirname(dirname(dirname(__file__)))
    except NameError:
        # For IPython development when this __file__ is not defined
        import mmtrack
        repo_dpath = dirname(dirname(mmtrack.__file__))
    config_dpath = join(repo_dpath, 'configs')
    if not exists(config_dpath):
        raise Exception('Cannot find config path')
    return config_dpath


def _get_config_module(fname):
    """Load a configuration as a python module."""
    from mmcv import Config
    config_dpath = _get_config_directory()
    config_fpath = join(config_dpath, fname)
    config_mod = Config.fromfile(config_fpath)
    return config_mod


def _get_model_cfg(fname):
    """Grab configs necessary to create a video detector or tracker.

    These are deep copied to allow for safe modification of parameters without
    influencing other tests.
    """
    config = _get_config_module(fname)
    model = copy.deepcopy(config.model)
    return model


def _rand_bboxes(rng, num_boxes, w, h):
    cx, cy, bw, bh = rng.rand(num_boxes, 4).T

    tl_x = ((cx * w) - (w * bw / 2)).clip(0, w)
    tl_y = ((cy * h) - (h * bh / 2)).clip(0, h)
    br_x = ((cx * w) + (w * bw / 2)).clip(0, w)
    br_y = ((cy * h) + (h * bh / 2)).clip(0, h)

    bboxes = np.vstack([tl_x, tl_y, br_x, br_y]).T
    return bboxes


def _demo_mm_inputs(batch_size=1,
                    frame_id=0,
                    num_ref_imgs=1,
                    image_shapes=[(1, 3, 128, 128)],
                    num_items=None,
                    num_classes=10,
                    with_semantic=False):
    """Create a superset of inputs needed to run test or train batches.

    Args:
        batch_size (int): batch size. Default to 2.
        image_shapes (List[tuple], Optional): image shape.
            Default to (128, 128, 3)
        num_items (None | List[int]): specifies the number
            of boxes in each batch item. Default to None.
        num_classes (int): number of different labels a
            box might have. Default to 10.
        with_semantic (bool): whether to return semantic.
            Default to False.
    """
    # from mmdet.core import BitmapMasks
    rng = np.random.RandomState(0)

    if isinstance(image_shapes, list):
        assert len(image_shapes) == batch_size
    else:
        image_shapes = [image_shapes] * batch_size

    if isinstance(num_items, list):
        assert len(num_items) == batch_size

    packed_inputs = []
    for idx in range(batch_size):
        image_shape = image_shapes[idx]
        t, c, h, w = image_shape

        image = rng.randint(0, 255, size=image_shape, dtype=np.uint8)

        mm_inputs = dict(inputs=dict())
        mm_inputs['inputs']['img'] = torch.from_numpy(image)
        if num_ref_imgs > 0:
            ref_img = [image] * num_ref_imgs
            ref_img = np.concatenate(ref_img)
            mm_inputs['inputs']['ref_img'] = torch.from_numpy(ref_img)

        img_meta = {
            'img_id': idx,
            'img_shape': image_shape[2:],
            'ori_shape': image_shape[2:],
            'filename': '<demo>.png',
            'scale_factor': np.array([1.1, 1.2]),
            'flip': False,
            'flip_direction': None,
            'is_video_data': True,
            'frame_id': frame_id
        }

        data_sample = TrackDataSample()
        data_sample.set_metainfo(img_meta)

        # gt_instances
        gt_instances = InstanceData()
        if num_items is None:
            num_boxes = rng.randint(1, 10)
        else:
            num_boxes = num_items[idx]

        bboxes = _rand_bboxes(rng, num_boxes, w, h)
        labels = rng.randint(1, num_classes, size=num_boxes)
        instances_id = rng.randint(100, num_classes + 100, size=num_boxes)
        gt_instances.bboxes = torch.FloatTensor(bboxes)
        gt_instances.labels = torch.LongTensor(labels)
        gt_instances.instances_id = torch.LongTensor(instances_id)

        # TODO: waiting for ci to be fixed
        # masks = np.random.randint(0, 2, (len(bboxes), h, w), dtype=np.uint8)
        # gt_instances.mask = BitmapMasks(masks, h, w)

        data_sample.gt_instances = gt_instances

        # ignore_instances
        ignore_instances = InstanceData()
        bboxes = _rand_bboxes(rng, num_boxes, w, h)
        ignore_instances.bboxes = bboxes
        data_sample.ignored_instances = ignore_instances

        # TODO: add gt_sem_seg
        # if with_semantic:
        #     # assume gt_semantic_seg using scale 1/8 of the img
        #     gt_semantic_seg = np.random.randint(
        #         0, num_classes, (1, 1, h // 8, w // 8), dtype=np.uint8)
        #     gt_sem_seg_data = dict(sem_seg=gt_semantic_seg)
        #     data_sample.gt_sem_seg = PixelData(**gt_sem_seg_data)

        mm_inputs['data_sample'] = data_sample

        # TODO: gt_ignore

        packed_inputs.append(mm_inputs)
    return packed_inputs