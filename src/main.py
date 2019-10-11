from torch.optim import Adam
from torch.nn.modules import MSELoss
import numpy as np
from experience_replay.exp_replay import ReplayBuffer, PrioritizedReplayBuffer, HindsightReplayBuffer, PrioritizedHindsightReplayBuffer
from algorithms.dqn import DQN
from algorithms.dqn_other import algo_DQN
import gym
import matplotlib.pyplot as plt


def update(algorithm, buffer, params, train_steps):
    batch = buffer.sample(params['batch_size'])
    if type(buffer) == ReplayBuffer or type(buffer) == HindsightReplayBuffer:
        obses_t, a, r, obses_tp1, dones = batch
        loss = algorithm.train(obses_t, a, r, obses_tp1, dones)
    elif type(buffer) == PrioritizedReplayBuffer or type(buffer) == PrioritizedHindsightReplayBuffer:
        obses_t, a, r, obses_tp1, dones, importance_weights, idxs = batch
        loss, losses = algorithm.per_train(obses_t, a, r, obses_tp1, dones, importance_weights)
        buffer.update_priorities(idxs, losses.numpy() + 1e-8)
    else:
        raise ValueError('?????')
    if isinstance(algorithm, algo_DQN):
        return loss
    # this func is not implemented for other_DWN
    algorithm.update_epsilon()
    if train_steps % params['target_network_interval'] == 0:
        algorithm.update_target_network()
    return loss


def add_transitions_to_buffer(transitions, buffer, completion_reward=0.0):
    if type(buffer) == ReplayBuffer or type(buffer) == PrioritizedReplayBuffer:
        for (f_t, g_t, a, r, f_tp1, g_tp1, done) in transitions:
            obs_t = np.hstack((f_t, g_t))
            obs_tp1 = np.hstack((f_tp1, g_tp1))
            buffer.add(obs_t, a, r, obs_tp1, done)
    if type(buffer) == HindsightReplayBuffer or type(buffer) == PrioritizedHindsightReplayBuffer:
        g_prime = transitions[-1][5]
        # Replace goal of every transition
        for i, (f_t, _, a, r, f_tp1, _, done) in enumerate(transitions):
            if i == len(transitions) - 1:
                r = completion_reward  # Last transition has its reward replaced
            buffer.add(f_t, g_prime, a, r, f_tp1, g_prime, done)


def main(params):
    # declare environment
    env = gym.make('CartPole-v0')

    # select type of experience replay using the parameters
    if params['buffer'] == ReplayBuffer:
        buffer = ReplayBuffer(params['buffer_size'])
        loss_function = params['loss_function']()
    elif params['buffer'] == PrioritizedReplayBuffer:
        buffer = PrioritizedReplayBuffer(params['buffer_size'], params['PER_alpha'], params['PER_beta'])
        loss_function = params['loss_function'](reduction='none')
    elif params['buffer'] == HindsightReplayBuffer:
        buffer = HindsightReplayBuffer(params['buffer_size'])
        loss_function = params['loss_function']()
    elif params['buffer'] == PrioritizedHindsightReplayBuffer:
        buffer = PrioritizedReplayBuffer(params['buffer_size'], params['PER_alpha'], params['PER_beta'])
        loss_function = params['loss_function'](reduction='none')
    else:
        raise ValueError('Buffer type not found.')

    # select learning algorithm using the parameters
    if params['algorithm'] == DQN:
        algorithm = DQN(env.observation_space.shape[0]*2,
                        env.action_space.n,
                        loss_function=loss_function,
                        optimizer=params['optimizer'],
                        lr=params['lr'],
                        gamma=params['gamma'],
                        epsilon_delta=params['epsilon_delta'],
                        epsilon_min=params['epsilon_min'])
    elif params['algorithm'] == algo_DQN:
        algorithm = algo_DQN()
    else:
        raise ValueError('Algorithm type not found.')

    losses = []
    returns = []
    train_steps = 0
    episodes_length = []

    for i in range(params['episodes']):
        print(i, '/', params['episodes'], end='\r')
        obs_t = env.reset()

        t = 0
        episode_loss = []
        episode_rewards = []
        episode_transitions = []
        while True:
            # env.render()
            action = algorithm.predict(np.hstack((obs_t, obs_t)))
            t += 1
            obs_tp1, reward, done, _ = env.step(action)
            episode_transitions.append((obs_t, (0,0,0,0), action, reward, obs_tp1, (0,0,0,0), done))
            episode_rewards.append(reward)
            if len(buffer) >= params['batch_size']:
                train_steps += 1
                loss = update(algorithm, buffer, params, train_steps)
                episode_loss.append(loss)

            # termination condition
            if done:
                episodes_length.append(t)
                # env.render()
                print('Episode finished in', t, 'steps')
                print('Cum. reward:', np.sum(episode_rewards), 'Loss:', np.mean(episode_loss), 'Epsilon:', algorithm.epsilon)
                break

            obs_t = obs_tp1

        add_transitions_to_buffer(episode_transitions, buffer)
        losses.append(np.mean(episode_loss))
        returns.append(np.sum(episode_rewards))

    env.close()

    # ====== Evaluation ========
    # And see the results
    def smooth(x, N):
        cumsum = np.cumsum(np.insert(x, 0, 0))
        return (cumsum[N:] - cumsum[:-N]) / float(N)

    plt.plot(smooth(episodes_length, 10))
    plt.title('Episode durations per episode')
    plt.show()


if __name__ == '__main__':
    parameters = {'buffer': HindsightReplayBuffer,
                  'buffer_size': 1500,
                  'PER_alpha': 0.6,
                  'PER_beta': 0.4,
                  'algorithm': DQN,
                  'batch_size': 64,
                  'hidden_size': (64,),
                  'optimizer': Adam,
                  'loss_function': MSELoss,
                  'lr': 1e-3,
                  'gamma': 0.8,
                  'epsilon_delta': 1e-4,
                  'epsilon_min': 0.10,
                  'target_network_interval': 100,
                  'environment': 'MountainCarContinuous-v0',
                  'episodes': 400}
    main(parameters)