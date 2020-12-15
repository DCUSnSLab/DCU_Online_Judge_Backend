import random
import time
from multiprocessing import Manager, Process

def Worker(task_queue,task_id):
    #for data in iter(task_queue.get, 'STOP'):
    # while True:
    #     data = task_queue.get()
    for data in iter(task_queue.get, 'STOP'):
        time.sleep(random.randint(1, 5))
        print("WorkerID[%d] Processes data - %s"%(task_id, data))
    print("Worker Ended")
    return


def produce_data(save_que):
    for _ in range(10):
        time.sleep(0.5)
        data = random.randint(1, 10)
        print("sending data", data)
        save_que.put(data)


if __name__ == '__main__':

    manager = Manager()
    save_que = manager.Queue()

    processes = []
    for i in range(4):
        processes.append(Process(name='process_%d'%i, target=Worker, args=(save_que, i)))

    for p in processes:
        p.start()
        print('Start',p, p.is_alive())
    produce_data(save_que)
    #save_p.terminate()
    #print('Start',save_p, save_p.is_alive())
    for p in processes:
        p.join()
