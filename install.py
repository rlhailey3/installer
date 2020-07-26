#!/usr/bin/env python3

import json
import subprocess
import os

class SgdiskException(Exception):
    def __init__(self, message: str):
        self.message = message


class LvmException(Exception):
    def __init__(self, message: str):
        self.message = message


class FormatException(Exception):
    def __init__(self, message: str):
        self.message = message


class MountException(Exception):
    def __init(self, message: str):
        self.message = message


class PacstrapException(Exception):
    def __init__(self, message: str):
        self.message = "Failed to install packages to /mnt"


def runCommand(command: list) -> bool:
    process = subprocess.Popen(command, stdout=subprocess.DEVNULL)
    process.wait()
    return True if not process.returncode else False

def wipeDisk(disk: dict) -> None:
    command = ["sgdisk", "-o", disk["path"]]
    failMessage = "Failed to wipe {0}".format(disk["path"])
    if not runCommand(command):
        raise SgdiskException(failMessage)

def partitionDisk(disk):
    for p in disk["partitions"]:
        failMessage = "Failed to partition {0}".format(disk["path"])
        partition = "{0}:{1}:{2}".format(
            str(p["number"]),
            str(p["start"]),
            str(p["end"])
        )

        command = [
            "sgdisk", "-n", partition,
            "-t", "{0}:{1}".format(str(p["number"]), str(p["type"])),
            "-c", "{0}:{1}".format(str(p["number"]), str(p["name"])),
            disk["path"]
        ]

        if not runCommand(command):
            raise SgdiskException(failMessage)

def partition(disks) -> None:
    for disk in disks:
        if disk["wipe"]:
            wipeDisk(disk)
        partitionDisk(disk)

def pvcreate(physical: str) -> None:
    command = ["pvcreate", physical]
    failMessage = "Failed to create physical volume on {0}".format(physical)
    if not runCommand(command):
        raise LvmException(failMessage)

def vgcreate(lv: dict) -> None:
    for p in lv["physical"]:
        pvcreate(p)

    physcialDisks = " ".join(lv["physical"])
    command = ["vgcreate", lv["name"], physcialDisks]
    failMessage = "Failed to create volume group {0}".format(lv["name"])
    if not runCommand(command):
        raise LvmException(failMessage)

def lvcreate(lv: dict) -> None:
    # lvcreate -L size groupName -n volumename [device]
    for logical in lv["logical"]:
        failMessage = "Failed to create logical volume {0} on group {1}".format(
            logical["name"], lv["name"]
        )
        option = "-L"
        if logical["size"] == "100%FREE":
            option = "-l"
        command = [
            "lvcreate",
            option,
            logical["size"],
            lv["name"],
            "-n",
            logical["name"]
        ]
        if "device" in logical:
            command.append(logical["device"])
        if not runCommand(command):
            raise LvmException(failMessage)

def lvm(lvm: list) -> None:
    for lv in lvm:
        vgcreate(lv)
        lvcreate(lv)

def formatPartition(f: dict) -> None:
    if f["format"] == "fat":
        command = ["mkfs.fat", "-F32"]
    elif f["format"] == "ext4":
        command = ["mkfs.ext4", "-F"]
    elif f["format"] == "swap":
        command = ["mkswap"]
    command.append(f["path"])
    failMessage = "Failed to format {0} as {1}".format(f["path"], f["format"])
    if not runCommand(command):
        raise FormatException(failMessage)
    if f["format"] == "swap":
        command = ["swapon", f["path"]]
        if not runCommand(command):
            failMessage = "Failed to enable swap at {0}".format(f["path"])
            raise FormatException(failMessage)

def mount(m: dict) -> None:
    if not os.path.exists(m["path"]):
        os.makedirs(m["path"])
    command = ["mount", m["device"], m["path"]]
    failMessage = "Failed to mount {0} to {1}".format(m["device"], m["path"])
    if not runCommand(command):
        raise MountException(failMessage)

def pacstrap(packages: list) -> None:
    command = ["pacstrap", "/mnt"]
    for item in packages:
        command.append(item)
    if not runCommand(command):
        raise PacstrapException()

def main():
    with open("./config.json") as file:
        config = json.loads(file.read())

    if "disks" in config:
        partition(config["disks"])

    if "lvm" in config:
        lvm(config["lvm"])

    if "format" in config:
        for f in config["format"]:
            formatPartition(f)

    if "mount" in config:
        for m in config["mount"]:
            mount(m)

    if "packages" in config:
        pacstrap(config["packages"])

main()
