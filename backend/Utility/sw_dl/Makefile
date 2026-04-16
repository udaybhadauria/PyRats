CC = gcc
INCLUDE_DIR := ../../include

CFLAGS = -Wall -Wextra -g
CFLAGS += -I$(INCLUDE_DIR)

LDFLAGS = -lpthread  -ljson-c -lcurl

SRCS = software_dl.c
OBJS = $(SRCS:.c=.o)
EXEC = software_dl

all: $(EXEC)

$(EXEC): $(OBJS)
	$(CC) $(OBJS) -o $(EXEC) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c $< -o $@

clean:
	rm -f $(OBJS) $(EXEC)

