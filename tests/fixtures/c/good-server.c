#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/neutrino.h>

int main(void) {
    name_attach_t *attach;
    int rcvid;
    char msg[256];
    const char reply[] = "hello from QNX";

    attach = name_attach(NULL, "hello", 0);
    if (attach == NULL) {
        fprintf(stderr, "name_attach failed: %s\n", strerror(errno));
        return EXIT_FAILURE;
    }

    for (;;) {
        rcvid = MsgReceive(attach->chid, msg, sizeof(msg), NULL);
        if (rcvid == -1) {
            break;
        }
        if (rcvid == 0) {
            continue;
        }
        if (MsgReply(rcvid, EOK, reply, strlen(reply) + 1) == -1) {
            break;
        }
    }

    name_detach(attach, 0);
    return EXIT_SUCCESS;
}
