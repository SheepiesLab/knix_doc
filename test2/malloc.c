#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <signal.h>

static size_t memsize = 0;
static void *mem = NULL;

static void catch_function(int signo)
{
    if (mem == NULL)
    {
        mem = malloc(memsize);
        if (!mem)
        {
            fputs("An error occurred while allocating memory.\n", stderr);
            exit(EXIT_FAILURE);
        }
        memset(mem, 0, memsize);

        fprintf(stderr, "%zu bytes allocated.\n", memsize);
        fprintf(stderr, "SIGINT to start retrival.\n");
        return;
    }

    fputs("Start retrieving memory.\n", stderr);
    memset(mem, 0, memsize);
    fputs("Done retrieving memory.\n", stderr);
    fputs("Process finish.\n", stderr);
    exit(EXIT_SUCCESS);
}

int main(int argc, char **argv)
{
    int i;
    pid_t pid;
    char buf[256];

    if (signal(SIGINT, catch_function) == SIG_ERR)
    {
        fputs("An error occurred while setting a signal handler.\n", stderr);
        return EXIT_FAILURE;
    }

    pid = getpid();
    fprintf(stderr, "PID: %d\n", pid);
    fprintf(stderr, "SIGINT to start allocation.\n");

    memsize = strtoul(argv[1], NULL, 0);

    while (1)
        ;

    return EXIT_SUCCESS;
}