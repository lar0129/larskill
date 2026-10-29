# [bug] futex 插入等待队列时，删除超时节点后继续访问其链表指针，导致内核崩溃

### 该问题是怎么引起的？

OpenHarmony 6.1 LTS的 `OsFutexInsertTasktoPendList()` 在按优先级插入等待者时，会调用 `OsFutexInsertFindFormBackToFront()` 从队尾向队头扫描。扫描中删除已超时节点后，循环仍通过该节点已经被置空的 `queueList.pstPrev` 前进，下一轮**访问非法节点地址并触发内核 data abort**。

**期望行为：** `OsFutexInsertTasktoPendList()` 应能处理“等待已超时、节点尚未清理”的中间状态。扫描时跳过或安全清理这些节点，将新等待者插入正确的优先级位置。

**实际行为：** 清理函数删除了超时节点，但循环变量 `listTail` 仍指向该节点。
- 清理函数 `LOS_ListDelete()` 已把超时节点的前后指针置空，循环增量将 `listTail` 更新为 `NULL`，下一轮把 `NULL` 转换为 `FutexNode *` 后访问 `pendList`发生读异常。

关键代码位于 `kernel/base/ipc/los_futex.c` 第 335～359 行：

```c
STATIC INT32 OsFutexInsertFindFormBackToFront(LOS_DL_LIST *queueList,
                                            const LosTaskCB *runTask, FutexNode *node)
{
    LOS_DL_LIST *listHead = queueList;
    LOS_DL_LIST *listTail = queueList->pstPrev;

    // 当前节点被删除后，循环增量仍读取其已清空的 pstPrev，使 listTail 变为 NULL。
    for (; listHead != listTail; listTail = listTail->pstPrev) {
        // 若 listTail 为 NULL，这里会按成员偏移构造出非法节点地址。
        FutexNode *tempNode = OS_FUTEX_FROM_QUEUELIST(listTail);
        // 返回值只更新 tempNode，不更新 listTail。
        // 清理函数内部调用 LOS_ListDelete()
        tempNode = OsFutexDeleteAlreadyWakeTaskAndGetNext(tempNode, NULL, FALSE);
        if (tempNode == NULL) {
            return LOS_NOK;
        }
        LosTaskCB *taskTail = OS_TCB_FROM_PENDLIST(LOS_DL_LIST_FIRST(&(tempNode->pendList)));
        INT32 ret = OsSchedParamCompare(runTask, taskTail);
        if (ret >= 0) {
            LOS_ListHeadInsert(&(tempNode->queueList), &(node->queueList));
            return LOS_OK;
        } else {
            // 此处仍通过 listTail 读取已删除节点被清空的 pstPrev。
            if (listTail->pstPrev == listHead) {
                LOS_ListTailInsert(&(tempNode->queueList), &(node->queueList));
                return LOS_OK;
            }
        }
    }

    return LOS_NOK;
}
```

1. 清理函数遇到已超时节点时，将其从链表摘除，`LOS_ListDelete()` 随即把该节点的前后指针置空。
2. 函数返回后，只将 `tempNode` 更新为邻接节点，`listTail` 仍指向已删除节点。
3. 当没有提前结束扫描时，循环增量把 `listTail` 更新为 `NULL`。
4. 下一轮继续用它换算 `FutexNode *`，再读取该非法节点的 `pendList`，最终触发内核异常。

### 重现步骤

将下面完整程序保存为 `futex_insert_test.c`，使用 `qemu_small_system_demo` 产品的用户态工具链编译为 `futex_insert_test`，放入该产品镜像的 `/bin` 目录。在 ARM32 单核 QEMU 中启动镜像，执行 `/bin/futex_insert_test`。

1. 在同一个 futex 上创建 W0～W3 四个等待线程，优先级依次为 5、10、15、20，数值越小优先级越高。其中 W2 使用 250 ms 超时，其余线程使用 5 s 超时，形成一个中间节点先超时的等待队列。
2. 主线程以优先级 2、`SCHED_FIFO` 忙等 600 ms，使 W2 超时后暂时无法运行并清理自己的 futex 节点。
3. 随后创建优先级为 14 的新等待者 W4；它先于 W2 运行，按当前优先级排列进入后向扫描。扫描到 W2 时，清理函数删除该节点，但循环仍使用它的链表指针，从而触发上述错误。

完整测试代码如下：

```c
#define _GNU_SOURCE 1
#include <errno.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdio.h>
#include <sys/syscall.h>
#include <time.h>
#include <unistd.h>

#define FUTEX_WAIT_PRIVATE 128
#define FUTEX_WAKE_PRIVATE 129

static volatile int fw;
static atomic_int entered;
static atomic_int woken;
static int order[8];

static double now_ms(void){struct timespec ts;clock_gettime(CLOCK_MONOTONIC,&ts);return ts.tv_sec*1000.0+ts.tv_nsec/1000000.0;}
static void set_prio(int p, int policy){struct sched_param sp={.sched_priority=p}; pthread_setschedparam(pthread_self(),policy,&sp);}
static void delay_ms(long ms){struct timespec ts={ms/1000,(ms%1000)*1000000L};while(nanosleep(&ts,&ts)!=0&&errno==EINTR){}}

static long wait_futex(unsigned int usec)
{
    errno = 0;
    return syscall(__NR_futex, (void*)&fw, FUTEX_WAIT_PRIVATE, 0, (void*)(unsigned long)usec, 0, 0);
}

static void *waiter(void *arg)
{
    long id = (long)arg;
    int prio = (id == 0) ? 5 : (id == 1) ? 10 : (id == 2) ? 15 : (id == 3) ? 20 : 14;
    unsigned int to = (id == 2) ? 250000u : 5000000u; /* S times out after 250 ms */
    set_prio(prio, SCHED_RR);
    atomic_fetch_add(&entered, 1);
    long r = wait_futex(to);
    int e = errno;
    if (r == 0) { int k = atomic_fetch_add(&woken, 1); order[k] = (int)id; printf("W%ld woken\n", id); }
    else printf("W%ld ret=%ld errno=%d\n", id, r, e);
    fflush(stdout);
    return NULL;
}

int main(void)
{
    pthread_t t[5];
    set_prio(2, SCHED_FIFO); /* main higher than all helpers, no time slice */
    printf("start\n"); fflush(stdout);
    for (int i = 0; i < 4; i++) {
        pthread_create(&t[i], NULL, waiter, (void*)(long)i);
        while (atomic_load(&entered) < i + 1) delay_ms(2);
        delay_ms(60);
    }
    printf("all queued, spinning\n"); fflush(stdout);
    double t0 = now_ms();
    while (now_ms() - t0 < 600.0) { }
    printf("spin done, create C\n"); fflush(stdout);
    pthread_create(&t[4], NULL, waiter, (void*)4L);
    delay_ms(300);
    printf("waking\n"); fflush(stdout);
    errno = 0;
    long w = syscall(__NR_futex, (void*)&fw, FUTEX_WAKE_PRIVATE, 8, 0, 0, 0);
    printf("wake ret=%ld errno=%d\n", w, errno);
    delay_ms(200);
    printf("done woken=%d order:", atomic_load(&woken));
    for (int i = 0; i < atomic_load(&woken); i++) printf(" %d", order[i]);
    printf("\n");
    return 0;
}
```

**预期输出：** W2 打印 `W2 ret=-1 errno=110`（`ETIMEDOUT`）；W0、W1、W4、W3 能被后续 `FUTEX_WAKE` 唤醒，程序输出 `done woken=4` 及唤醒顺序。新增等待者的插入不应引发内核异常。

**实际输出：** 现有串口日志显示，程序打印到 `spin done, create C` 后发生内核 data abort。

### 报错信息

```text
start
all queued, spinning
spin done, create C
##################excFrom: kernel!###################
data_abort fsr:0x5, far:0xfffffffc
Abort caused by a read instruction. Translation fault, section
excType: data abort
taskName          = thread5
taskID            = 19
R5    = 0xffffffec
```

日志中的 `excFrom: kernel!` 表明异常发生在内核，`far=0xfffffffc` 是本次非法读地址。
