/* bad-client.c — deliberately broken QNX code. Every rule in ccheck.py
 * should fire on this file at least once. Do not "fix" it. */
#include <stdio.h>
#include <stdlib.h>
#include <sys/neutrino.h>
#include <sys/epoll.h>

static void isr_handler(void *area, int id) {
    printf("interrupt %d!\n", id); /* C08: printf in an ISR */
    free(area);                    /* C08: free in an ISR */
}

int main(void) {
    ChannelCreate(0); /* C02: unchecked; C03: never destroyed */
    int coid = ConnectAttach(0, 1, 1, _NTO_SIDE_CHANNEL, 0); /* C04 */
    name_attach_t *a = name_attach(NULL, "x", 0); /* C05 */
    (void)a;
    MsgSend(coid, "hi", 3, NULL, 0); /* C06: blocking, no timeout */
    pthread_t tid;
    pthread_create(&tid, NULL, NULL, NULL); /* C07: default attributes */
    (void)in8(0x3f8); /* C10: port I/O without ThreadCtl(_NTO_TCTL_IO) */
    int ep = epoll_create(10); /* C11: Linux-only API */
    (void)ep;
    if (fork() == 0) { /* C12: prefer spawn() */
        _exit(0);
    }
    sleep(1); /* C14: imprecise wait */
    SchedSet(0, 0, SCHED_FIFO, NULL); /* C15: unchecked */
    return 0;
}

int server_loop(int chid) {
    char buf[64];
    int rcvid = MsgReceive(chid, buf, sizeof(buf), NULL);
    (void)rcvid;
    return 0; /* C13: MsgReceive but no MsgReply */
}

void setup(void) {
    InterruptAttach(4, isr_handler, NULL, 0, 0); /* C09: never detached */
}
