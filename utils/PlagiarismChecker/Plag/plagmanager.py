from multiprocessing import Process, Queue, current_process
import time
import os
import queue # imported for using queue.Empty exception

class PlagManager:
    def __init__(self):
        self.cnt = 0;

    def test(self):
        print("test method")

def count(name):
    for i in range(1, 10):
        time.sleep(1)
        print(name," : ",i)

def do_job(tasks_to_accomplish, tasks_that_are_done):
    while True:
        try:
            '''
                try to get task from the queue. get_nowait() function will 
                raise queue.Empty exception if the queue is empty. 
                queue(False) function would do the same task also.
            '''
            task = tasks_to_accomplish.get_nowait()
            print("get_nowait",current_process().name)
        except queue.Empty:
            #print("Queue Empty")
            continue
            #break
        else:
            '''
                if no exception has been raised, add the task completion 
                message to task_that_are_done queue
            '''
            print(task,current_process().name)
            #tasks_that_are_done.put(task + ' is done by ' + current_process().name)
            time.sleep(.5)
    return True

if __name__ == '__main__':
    number_of_task = 10
    number_of_processes = 4
    tasks_to_accomplish = Queue()
    tasks_that_are_done = Queue()
    processes = []

    print("start process")
    # creating processes
    for w in range(number_of_processes):
        p = Process(target=do_job, args=(tasks_to_accomplish, tasks_that_are_done))
        processes.append(p)
        p.start()

    print("put task")
    for i in range(number_of_task):
        time.sleep(1)
        tasks_to_accomplish.put("Task no " + str(i))

    # completing process
    for p in processes:
        p.join()

    # print the output
    while not tasks_that_are_done.empty():
        print(tasks_that_are_done.get())
