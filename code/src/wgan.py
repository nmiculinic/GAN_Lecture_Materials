import sys
import tensorflow as tf
import numpy as np
from utils import Timer


class WGAN:
    max_summary_images = 4

    def __init__(self,
                 generator,
                 critic,
                 dataset,
                 z_size,
                 optimizer=tf.train.AdamOptimizer(learning_rate=0.0001, beta1=0.5, beta2=0.9)):
        """
        Definition of the Wasserstein GAN with Gradient Penalty (WGAN-GP)

        :param generator: neural network which takes a batch of random vectors and creates a batch of images
        :param critic: neural network which takes a batch of images and outputs a "realness" score for each of them
        :param dataset: dataset which will be reconstructed
        :param z_size: size of the random vector used for generation
        :param optimizer: Default Adam with hyperparameters as recommended in the WGAN-GP paper
        """

        self.generator = generator
        self.critic = critic

        self.optimizer = optimizer
        self.z_size = z_size
        self.dataset = dataset

        # z shape is [batch_size, z_size]
        self.z = tf.placeholder(tf.float32, [None, self.z_size], name="Z")
        # image shape is [batch_size, height, width, channels]
        self.real_image = tf.placeholder(tf.float32,
                                         [None, self.dataset.img_size, self.dataset.img_size, self.dataset.channels],
                                         name="Real_image")
        """
        ##################################################################
        
        TODO: Create the cost function for generator and the critic. 
        You don't have to worry about adding a regularizing term for the Lipschitz continuity, it's added later to the 
        self.c_cost you define here.
        
        YOUR CODE BEGIN.
        
        ##################################################################
        """

        self.fake_image = self.generator(self.z)
        self.c_real = self.critic(self.real_image)
        self.c_fake = self.critic(self.fake_image, reuse=True)

        self.g_cost = tf.reduce_mean(self.c_fake)
        self.c_cost = tf.reduce_mean(self.c_real - self.c_fake) 

        """   
        ##################################################################
        
        YOUR CODE END.

        ##################################################################
        """

        # Critic regularization, satisfying the Lipschitz constraint with gradient penalty
        with tf.name_scope("Gradient_penalty"):
            self.eta = tf.placeholder(tf.float32, shape=[None, 1, 1, 1], name="Eta")
            interp = self.eta * self.real_image + (1 - self.eta) * self.fake_image
            c_interp = self.critic(interp, reuse=True)

            # taking the zeroth and only element because tf.gradients returns a list
            c_grads = tf.gradients(c_interp, interp)[0]

            # L2 norm, reshaping to [batch_size]
            slopes = tf.sqrt(tf.reduce_sum(tf.square(c_grads), axis=[1, 2, 3]))
            tf.summary.histogram("Critic gradient L2 norm", slopes)

            grad_penalty = tf.reduce_mean(tf.square(slopes - 1) ** 2)
            lambd = 10
            self.c_cost += lambd * grad_penalty
        """
        ##################################################################

        TODO: Create the optimizers for both critic and the generator. Each of the optimizers should only update only 
        critic weights or only generator weights!
        
        YOUR CODE BEGIN.
        
        ##################################################################
        """

        self.c_optimizer = optimizer.minimize(
                -(self.c_cost), 
                var_list=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='Critic')
        )
        self.g_optimizer = optimizer.minimize(
                self.g_cost, 
                var_list=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES, scope='Generator')

        )
        """   
        ##################################################################
        
        YOUR CODE END.

        ##################################################################
        """

        # Defining summaries for tensorflow until the end of the method
        tf.summary.image("Generated image", self.fake_image, max_outputs=WGAN.max_summary_images)
        tf.summary.image("Real image", self.real_image, max_outputs=WGAN.max_summary_images)
        tf.summary.scalar("Critic cost", self.c_cost)
        tf.summary.scalar("Generator cost", self.g_cost)

        # Distributions of weights and their gradients
        from tensorflow.python.framework import ops
        for gradient, variable in self.optimizer.compute_gradients(self.c_cost):
            if isinstance(gradient, ops.IndexedSlices):
                grad_values = gradient.values
            else:
                grad_values = gradient
            tf.summary.histogram(variable.name, variable)
            tf.summary.histogram(variable.name + "/gradients", grad_values)

        self.merged = tf.summary.merge_all()

    def __call__(self, batch_size, steps, model_path):
        """
        Trains the neural network by calling the .one_step() method "steps" number of times.
        Adds a Tensorboard summary every 100 steps

        :param batch_size:
        :param steps:
        :param model_path: location of the model on the filesystem
        """
        with tf.Session() as sess:
            writer = tf.summary.FileWriter(model_path, sess.graph)
            tf.global_variables_initializer().run()
            saver = tf.train.Saver()

            timer = Timer()
            for step in range(steps):
                print(step, end=" ")
                sys.stdout.flush()

                self.one_step(sess, batch_size, step)

                if step % 100 == 0:
                    self.add_summary(sess, step, writer, timer)
                    saver.save(sess, model_path)

    def one_step(self, sess, batch_size, step):
        """
        Performs one step of WGAN update, which is actually several optimizations of the Critic and one optimization of
        the Generator.

        :param sess: Tensorflow session in which the update will be performed
        :param batch_size:
        :param step: current step, used for determining how much the critic should be updated
        """
        """
        ##################################################################

        TODO: Devise an updating scheme for the critic and the generator. 
        Hint: the critic should always be trained more than the generator.
        
        YOUR CODE BEGIN.
        
        ##################################################################
        """

        for _ in range(5):
            data_batch = self.dataset.next_batch_real(batch_size)
            z = self.dataset.next_batch_fake(batch_size, self.z_size)
            eta = np.random.rand(batch_size, 1, 1, 1)
            sess.run(self.c_optimizer, feed_dict={
                self.z: z,
                self.eta: eta,
                self.real_image: data_batch
            }

        data_batch = self.dataset.next_batch_real(batch_size)
        z = self.dataset.next_batch_fake(batch_size, self.z_size)
        eta = np.random.rand(batch_size, 1, 1, 1)
        sess.run(self.g_optimizer, feed_dict={
            self.z: z,
            self.eta: eta,
            self.real_image: data_batch
        }

        """
        ##################################################################
        YOUR CODE END. 
        ##################################################################
        """

    def add_summary(self, sess, step, writer, timer):
        """
        Adds a summary for the specified step in Tensorboard
        Tries to reconstruct new samples from dataset

        :param sess:
        :param step:
        :param writer:
        :param timer:
        :return:
        """
        data_batch = self.dataset.next_batch_real(WGAN.max_summary_images)
        z = self.dataset.next_batch_fake(WGAN.max_summary_images, self.z_size)
        eta = np.random.rand(WGAN.max_summary_images, 1, 1, 1)

        summary = sess.run(self.merged, feed_dict={self.real_image: data_batch, self.z: z, self.eta: eta})
        writer.add_summary(summary, step)
        print("\rSummary generated. Step", step, " Time == %.2fs" % timer.time())
