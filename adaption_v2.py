# -*- coding:utf-8 -*-
import tensorflow as tf

from maml_v2 import MAML

from utils_v2 import sample_generator, read_pts

from scene_sampling_v2 import SLICProcessor

import pandas as pd
import numpy as np
from osgeo import gdal

from utils_v2 import read_pts, sample_generator_

from tensorflow.python.platform import flags

FLAGS = flags.FLAGS
flags.DEFINE_integer('dim_input', 16, 'dim of input data')
flags.DEFINE_integer('dim_output', 2, 'dim of output data')
flags.DEFINE_float('update_lr', 1e-1, 'learning rate in meta-learning task')
flags.DEFINE_float('meta_lr', 1e-4, 'the base learning rate of meta learning process')
flags.DEFINE_string('basemodel', 'MLP', 'MLP: no unsupervised pretraining; DAS: pretraining with DAS')
flags.DEFINE_integer('num_updates', 5, 'number of inner gradient updates during training.')
flags.DEFINE_string('norm', 'batch_norm', 'batch_norm, layer_norm, or None')
flags.DEFINE_integer('num_samples_each_task', 12, 'number of samples sampling from each task when training, inner_batch_size')
flags.DEFINE_bool('stop_grad', False, 'if True, do not use second derivatives in meta-optimization (for speed)')
flags.DEFINE_integer('meta_batch_size', 16, 'number of tasks sampled per meta-update, not nums tasks')
flags.DEFINE_string('logdir', './checkpoint_dir', 'directory for summaries and checkpoints.')
flags.DEFINE_integer('num_samples', 2637, 'total number of number of samples in FJ and FL.')
flags.DEFINE_integer('test_update_batch_size', 5, 'number of examples used for gradient update during adapting (K=1,3,5 in experiment, K-shot).')

if __name__ == "__main__":
    exp_string = "mode2.mbs16.ubs_12.numstep5.updatelr0.1.meta_lr0.0001"  # if FJ, mode 2; if FL, mode 3
    model = MAML(FLAGS.dim_input, FLAGS.dim_output, test_num_updates=5)
    input_tensors = None
    model.construct_model(input_tensors=input_tensors, prefix='metatrain_')

    var_list = tf.compat.v1.get_collection(tf.compat.v1.GraphKeys.TRAINABLE_VARIABLES)
    #saver = tf.train.import_meta_graph('./checkpoint_dir/' + exp_string + '/model4999.meta')
    saver = tf.compat.v1.train.Saver(var_list)
    sess = tf.compat.v1.InteractiveSession()
    init = tf.compat.v1.global_variables()  # extra variables require initialization in the optimizer
    sess.run(tf.compat.v1.variables_initializer(var_list=init))

    model_file = tf.train.latest_checkpoint(FLAGS.logdir + '/' + exp_string)
    if model_file:
        print("Restoring model weights from " + model_file)
        saver.restore(sess, model_file)  # use model_file initialize sess graph
    else:
        print("no intermediate model found!")

    """获取tasks"""

    """adapting within a region"""
    def overall_adapting(taskfile, num_updates=5):
        tasks = read_pts(taskfile)
        inputa, labela = sample_generator_(tasks, FLAGS.dim_input, FLAGS.dim_output)
        with tf.compat.v1.variable_scope('model', reuse=True):  # Variable reuse in np.normalize()
            task_output = model.forward(inputa[0], model.weights, reuse=True)
            task_loss = model.loss_func(task_output, labela)
            grads = tf.gradients(ys=task_loss,xs=list(model.weights.values()))
            gradients = dict(zip(model.weights.keys(), grads))
            fast_weights = dict(zip(model.weights.keys(), [model.weights[key] -
                                                           model.update_lr*gradients[key] for key in model.weights.keys()]))
            for j in range(num_updates - 1):
                # fast_weight is related to grads (stopped), but doesn't affect the gradient computation
                loss = model.loss_func(model.forward(inputa[0], fast_weights, reuse=True), labela)
                grads = tf.gradients(ys=loss, xs=list(fast_weights.values()))
                gradients = dict(zip(fast_weights.keys(), grads))
                fast_weights = dict(zip(fast_weights.keys(), [fast_weights[key] - model.update_lr*gradients[key] for key in fast_weights.keys()]))
            adapted_weights = sess.run(fast_weights)
            np.savez('models_of_blocks/overall_FJ/model_MAML', adapted_weights['w1'],adapted_weights['b1'],
                     adapted_weights['w2'],adapted_weights['b2'],
                     adapted_weights['w3'],adapted_weights['b3'],
                     adapted_weights['w4'],adapted_weights['b4'])
            print('overall model saved')

    def blocks_adapting():  # TODO: move from predit_LSM here
        "it's in predit_LSM"
        pass

    FJ_taskfile = './seg_output/FJ_tasks.xlsx'
    FL_taskfile = './seg_output/FL_tasks.xlsx'

    overall_adapting(FJ_taskfile)