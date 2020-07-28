#!/usr/bin/env python3

# TODO
# add lvm2 hook if lvm is used

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
    def __init__(self):
        self.message = "Failed to install packages to /mnt"


class ChrootException(Exception):
    def __init__(self, message: str):
        self.message = message


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

def runChrootCommand(command: list) -> None:
    chrootCommand = ["arch-chroot", "/mnt"]
    for item in command:
        chrootCommand.append(item)
    failMessage = "Failed to run command: {0}".format(" ".join(chrootCommand))
    if not runCommand(chrootCommand):
        raise ChrootException(failMessage)

def enableServices(services: list) -> None:
    command = ["systemctl", "enable"]
    for service in services:
        command.append(service)
    runChrootCommand(command)

def setHostname(hostname: str):
    with open("/mnt/etc/hostname", "x") as file:
        file.write(hostname)
        file.write("\n")

def createUser(user: dict) -> None:
    command =["useradd", "-m", "-g"]
    if "primarygroup" in user:
        command.append(user["primarygroup"])
    else:
        command.append("users")
    if "secondarygroups" in user:
        command.append("-G")
        command.append(",".join(user["secondarygroups"]))
    command.append(user["username"])
    runChrootCommand(command)
    command = ["passwd", user["username"]]
    runChrootCommand(command)

def setTimezone(timezone: str):
    zone = "/usr/share/zoneinfo/{0}".format(timezone)
    command = ["ln", "-sf", zone, "/etc/localtime"]
    runChrootCommand(command)
    command = ["hwclock", "--systohc"]
    runChrootCommand(command)

def setLocalization(localization: list) -> None:
    # sed 's/\#en_US.UTF-8/TEST/' /etc/locale.gen
    for item in localization:
        sedCommand = [
            "sed",
            "-i",
            "s/\#{0}/{0}/".format(item),
            "/etc/locale.gen"
        ]
        runChrootCommand(sedCommand)
        genCommand = ["locale-gen"]
        runChrootCommand(genCommand)
    with open("/mnt/etc/locale.conf", "x") as file:
        line = "LANG={0}".format(localization[0])
        file.write(line)
        file.write("\n")

def envVariables(environment: list) -> None:
    with open("/mnt/etc/environment", "a") as file:
        variables = "\n".join(environment)
        file.write(variables)
        file.write("\n")

def setHosts(hosts: list) -> None:
    with open("/mnt/etc/hosts", "a") as file:
        data = "\n".join(hosts)
        file.write(data)
        file.write("\n")

def setWheelSudo() -> None:
    with open("/mnt/etc/sudoers.d/wheel-password", "x") as file:
        file.write("%wheel ALL=(ALL) ALL")

def genFstab() -> None:
    fstab = subprocess.getoutput("genfstab -U /mnt")
    with open("/mnt/etc/fstab", "a") as file:
        file.write(fstab)

def setSystemdBoot(loader: dict) -> None:
    command = ["bootctl", "install"]
    runChrootCommand(command)
    loaderEntryPath = "/mnt{0}".format(loader["path"])
    if not os.path.exists(os.path.dirname(loaderEntryPath)):
        os.makedirs(os.path.dirname(loaderEntryPath))
    with open(loaderEntryPath, "x") as file:
        file.write("title {0}\n".format(loader["title"]))
        file.write("linux /{0}\n".format(loader["kernel"]))
        if "ucode" in loader:
            file.write("initrd /{0}\n".format(loader["ucode"]))
        file.write("initrd /initramfs-linux.img\n")
        if loader["root"]["type"] == "lvm":
            root = loader["root"]["path"]
        file.write("options root={0} {1}\n".format(
            root, " ".join(loader["options"]
        )))

def setBootLoader(loader: dict) -> None:
    if loader["type"] == "systemd-boot":
        setSystemdBoot(loader)

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

    if "services" in config:
        enableServices(config["services"])

    if "hostname" in config:
        setHostname(config["hostname"])

    if "timezone" in config:
        setTimezone(config["timezone"])

    if "localization" in config:
        setLocalization(config["localization"])

    if "environment" in config:
        envVariables(config["environment"])

    if "users" in config:
        for user in config["users"]:
            createUser(user)

    setWheelSudo()
    genFstab()

    if "hosts" in config:
        setHosts(config["hosts"])

    if "bootloader" in config:
        setBootLoader(config["bootloader"])

main()
