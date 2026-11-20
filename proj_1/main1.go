package main

import (
    "fmt"
    "os"
    "runtime"
    "time"
)

func main() {
    host, _ := os.Hostname()
    fmt.Printf("Xin chao tu %s! Kien truc: %s/%s\n", host, runtime.GOOS, runtime.GOARCH)
    for i := 1; i <= 5; i++ {
        fmt.Printf("[Tick %d] Build tu Windows VS Code chay tren Luckfox ngon lanh!\n", i)
        time.Sleep(1 * time.Second)
    }
}