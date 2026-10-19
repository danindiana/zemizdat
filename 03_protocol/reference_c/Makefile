CFLAGS=-std=c99 -O1 -g -Wall -Wextra -Wpedantic -Wconversion -Wno-sign-conversion
test: vectors.txt
	$(CC) $(CFLAGS) -fsanitize=address,undefined -fno-sanitize-recover=all zm_core.c test_zm_core.c -o test_zm_core
	./test_zm_core
vectors.txt: gen_vectors.py ../reference_py/zmproto.py
	python3 gen_vectors.py
size:
	arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -Os -c zm_core.c -o /tmp/zm.o && arm-none-eabi-size /tmp/zm.o
clean:
	rm -f test_zm_core
