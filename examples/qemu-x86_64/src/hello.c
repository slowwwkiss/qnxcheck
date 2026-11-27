/* hello.c — minimal correct QNX Neutrino message-passing server.
 *
 * Listens on the name "hello": a client sends any message and gets the
 * reply "hello from QNX". Written to pass `qnxcheck c`:
 *  - <sys/neutrino.h> is included (C01)
 *  - name_attach() result is checked, name_detach() is paired (C05)
 *  - every MsgReceive() path ends in MsgReply() or MsgError() (C13)
 *  - no fork(), no Linux-only APIs, no blocking MsgSend() (C06/C11/C12)
 */
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
            break; /* channel closed or error: shut down cleanly */
        }
        if (rcvid == 0) {
            continue; /* a pulse, not a message: keep waiting */
        }
        if (MsgReply(rcvid, EOK, reply, strlen(reply) + 1) == -1) {
            break;
        }
    }

    name_detach(attach, 0);
    return EXIT_SUCCESS;
}
