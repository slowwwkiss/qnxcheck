#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <errno.h>
#include <time.h>
#include <sys/neutrino.h>

int main(void) {
    int coid;
    char reply[64];
    uint64_t timeout_ns = 1000000000ULL; /* 1 second */

    coid = name_open("hello", 0);
    if (coid == -1) {
        fprintf(stderr, "name_open failed: %s\n", strerror(errno));
        return EXIT_FAILURE;
    }

    /* Bound the send: if the server never replies, we time out. */
    TimerTimeout(CLOCK_REALTIME, _NTO_TIMEOUT_SEND, NULL, &timeout_ns,
                 NULL);
    if (MsgSend(coid, "ping", 5, reply, sizeof(reply)) == -1) {
        fprintf(stderr, "MsgSend failed: %s\n", strerror(errno));
        name_close(coid);
        return EXIT_FAILURE;
    }

    printf("server replied: %s\n", reply);
    name_close(coid);
    return EXIT_SUCCESS;
}
