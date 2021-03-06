# coding: utf-8
import os

import tensorflow as tf


def image_scaling(img, label):
    """
    Randomly scales the images between 0.5 to 1.5 times the original size.

    Args:
      img: Training image to scale.
      label: Segmentation mask to scale.
    """

    scale = tf.random_uniform([1], minval=0.5, maxval=1.5, dtype=tf.float32, seed=None)
    h_new = tf.to_int32(tf.multiply(tf.to_float(tf.shape(img)[0]), scale))
    w_new = tf.to_int32(tf.multiply(tf.to_float(tf.shape(img)[1]), scale))
    new_shape = tf.squeeze(tf.stack([h_new, w_new]), squeeze_dims=[1])
    img = tf.image.resize_images(img, new_shape)
    label = tf.image.resize_nearest_neighbor(tf.expand_dims(label, 0), new_shape)
    label = tf.squeeze(label, squeeze_dims=[0])

    return img, label


def image_mirroring(img, label):
    """
    Randomly mirrors the images.

    Args:
      img: Training image to mirror.
      label: Segmentation mask to mirror.
    """

    distort_left_right_random = tf.random_uniform([1], 0, 1.0, dtype=tf.float32)[0]
    mirror = tf.less(tf.stack([1.0, distort_left_right_random, 1.0]), 0.5)
    mirror = tf.boolean_mask([0, 1, 2], mirror)
    img = tf.reverse(img, mirror)
    label = tf.reverse(label, mirror)
    return img, label


def random_crop_and_pad_image_and_labels(image, label, crop_h, crop_w, ignore_label=255):
    """
    Randomly crop and pads the input images.

    Args:
      image: Training image to crop/ pad.
      label: Segmentation mask to crop/ pad.
      crop_h: Height of cropped segment.
      crop_w: Width of cropped segment.
      ignore_label: Label to ignore during the training.
    """

    label = tf.cast(label, dtype=tf.float32)
    label = label - ignore_label  # Needs to be subtracted and later added due to 0 padding.
    combined = tf.concat(axis=2, values=[image, label])
    image_shape = tf.shape(image)
    combined_pad = tf.image.pad_to_bounding_box(combined, 0, 0, tf.maximum(crop_h, image_shape[0]),
                                                tf.maximum(crop_w, image_shape[1]))

    last_image_dim = tf.shape(image)[-1]
    last_label_dim = tf.shape(label)[-1]
    combined_crop = tf.random_crop(combined_pad, [crop_h, crop_w, 4])
    img_crop = combined_crop[:, :, :last_image_dim]
    label_crop = combined_crop[:, :, last_image_dim:]
    label_crop = label_crop + ignore_label
    label_crop = tf.cast(label_crop, dtype=tf.uint8)

    # Set static shape so that tensorflow knows shape at compile time.
    img_crop.set_shape((crop_h, crop_w, 3))
    label_crop.set_shape((crop_h, crop_w, 1))
    return img_crop, label_crop


def get_data_from_dataset(data_dir, name, is_val=False, valid_image_store_path='/path/to/arbitrary/'):
    '''
    :param data_dir:
    :param name:
    :param is_val:
    :param valid_image_store_path: when you use the val_g.py,you will use it.otherwise ignore it please.
    :return:
    '''
    base_url = data_dir
    images, masks, png_names = [], [], []
    if name == 'VOC2012':
        data_url = {
            'Annotations': base_url + 'Annotations/',
            'ImageSets': base_url + 'ImageSets/',
            'JPEGImages': base_url + 'JPEGImages/',
            'SegmentationClass': base_url + 'SegmentationClass/',
            'SegmentationLabel': base_url + 'SegmentationLabel/',
            'SegmentationObject': base_url + 'SegmentationObject/'
        }

        filepath = data_url['ImageSets']
        filepath += 'Segmentation/val.txt' if is_val else 'Segmentation/train_dup.txt'
        print("file path:" + filepath)
        with open(filepath, mode='r') as f:
            imgs_name = f.readlines()
        for i in range(len(imgs_name)):
            imgs_name[i] = imgs_name[i].strip('\n')
        for name in imgs_name:
            images.append(data_url['JPEGImages'] + name + '.jpg')
            masks.append(data_url['SegmentationLabel'] + name + '.png')
            png_names.append(valid_image_store_path + name + '.png')
        return images, masks, png_names

    elif name == 'sbd':
        data_url = {
            'anns': base_url + 'dataset/clsImg/',
            'images': base_url + 'images/'
        }

        filepath = base_url + 'sbd.txt'

        print("file path:" + filepath)
        with open(filepath, mode='r') as f:
            imgs_name = f.readlines()
        for i in range(len(imgs_name)):
            imgs_name[i] = imgs_name[i].strip()
        for name in imgs_name:
            images.append(data_url['images'] + name + '.jpg')
            masks.append(data_url['anns'] + name + '.png')
        return images, masks, []


def read_labeled_image_list(data_dir, is_val=False, valid_image_store_path='/path/to/arbitrary/'):
    """Reads txt file containing paths to images and ground truth masks.

    Args:
      data_dir: path to the directory with images and masks.
      valid_image_store_path: the path that store the valided images if you want
    Returns:
      Two lists with all file names for images and masks, respectively.
    """
    assert type(data_dir) == list
    images, masks = [], []
    for base_url in data_dir:
        ti, tm, tn = None, None, None
        if 'VOC2012' in base_url:
            ti, tm, tn = get_data_from_dataset(base_url, 'VOC2012', is_val, valid_image_store_path)
            if is_val:
                return ti, tm, tn
        elif 'sbd' in base_url:
            ti, tm, _ = get_data_from_dataset(base_url, 'sbd')
        else:
            print("no such path")
            exit()
        images.extend(ti)
        masks.extend(tm)
    return images, masks, None


def read_images_from_disk(input_queue, input_size, random_scale, random_mirror, random_crop, ignore_label,
                          img_mean):  # optional pre-processing arguments
    """Read one image and its corresponding mask with optional pre-processing.

    Args:
      input_queue: tf queue with paths to the image and its mask.
      input_size: a tuple with (height, width) values.
                  If not given, return images of original size.
      random_scale: whether to randomly scale the images prior
                    to random crop.
      random_mirror: whether to randomly mirror the images prior
                    to random crop.
      ignore_label: index of label to ignore during the training.
      img_mean: vector of mean colour values.

    Returns:
      Two tensors: the decoded image and its mask.
    """

    img_contents = tf.read_file(input_queue[0])
    label_contents = tf.read_file(input_queue[1])
    img = tf.image.decode_jpeg(img_contents, channels=3)
    img_r, img_g, img_b = tf.split(axis=2, num_or_size_splits=3, value=img)
    img = tf.cast(tf.concat(axis=2, values=[img_b, img_g, img_r]), dtype=tf.float32)
    # Extract mean.
    img -= img_mean

    label = tf.image.decode_png(label_contents, channels=1)

    if input_size is not None:
        h, w = input_size

        # Randomly scale the images and labels.
        if random_scale:
            img, label = image_scaling(img, label)

        # Randomly mirror the images and labels.
        if random_mirror:
            img, label = image_mirroring(img, label)

        # Randomly crops the images and labels.
        if random_crop:
            img, label = random_crop_and_pad_image_and_labels(img, label, h, w, ignore_label)

    return img, label


class ImageReader(object):
    '''Generic ImageReader which reads images and corresponding segmentation
       masks from the disk, and enqueues them into a TensorFlow queue.
    '''

    def __init__(self, data_dir, input_size,
                 random_scale, random_mirror, random_crop, ignore_label, is_val, img_mean,
                 coord):
        '''Initialise an ImageReader.

        Args:
          data_dir: path to the directory with images and masks.
          data_list: path to the file with lines of the form '/path/to/image /path/to/mask'.
          input_size: a tuple with (height, width) values, to which all the images will be resized.
          random_scale: whether to randomly scale the images prior to random crop.
          random_mirror: whether to randomly mirror the images prior to random crop.
          ignore_label: index of label to ignore during the training.
          img_mean: vector of mean colour values.
          coord: TensorFlow queue coordinator.
        '''
        self.data_dir = data_dir
        self.input_size = input_size
        self.coord = coord
        self.image_list, self.label_list, _ = read_labeled_image_list(self.data_dir, is_val)
        self.images = tf.convert_to_tensor(self.image_list, dtype=tf.string)
        self.labels = tf.convert_to_tensor(self.label_list, dtype=tf.string)
        self.queue = tf.train.slice_input_producer([self.images, self.labels],
                                                   shuffle=is_val is not True)  # not shuffling if it is val
        self.image, self.label = read_images_from_disk(self.queue, self.input_size, random_scale, random_mirror,
                                                       random_crop, ignore_label, img_mean)

    def dequeue(self, batch_size):
        '''Pack images and labels into a batch.

        Args:
          batch_size: the batch size.

        Returns:
          Two tensors of size (batch_size, h, w, {3, 1}) for images and masks.'''

        image_batch, label_batch = tf.train.batch([self.image, self.label], batch_size, dynamic_pad=True)
        return image_batch, label_batch
