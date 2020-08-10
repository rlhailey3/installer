#!/usr/bin/env python3

# TODO
# show pacstrap output, add commandline noconfirm option
# add additional filesystem types?
# add additional bootloader?
# add detailed comments for classes / functions

import json
import subprocess
import os

class ConfigurationException(Exception):
    def __init__(self, message: str):
        self.message = message


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
            print("Wiping {0}".format(disk["path"]))
            wipeDisk(disk)
        print("Partitioning {0}".format(disk["path"]))
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
        print("Creating logical volume {0}".format(logical["name"]))
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
        print("Creating Volume Group {0}".format(lv["name"]))
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
    while True:
        try:
            print("Set password for {0}".format(user["username"]))
            runChrootCommand(command)
            break
        except ChrootException:
            continue

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

def enableLvmHook():
    command = [
        "sed",
        "-i",
        "/^HOOKS/{s/block/block lvm2/}",
        "/mnt/etc/mkinitcpio.conf"
    ]
    runCommand(command)
    
def mkinitcpio() -> None:
    command = [
        "mkinitcpio",
        "-p",
        "linux"
    ]
    runChrootCommand(command)

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

    if loader["root"]["type"] == "lvm":
        enableLvmHook()
        
    mkinitcpio()
    
def main():
    with open("./config.json") as file:
        config = json.loads(file.read())

    if "disks" in config:
        print("Partitioning Disks")
        partition(config["disks"])
    else:
        failMessage = "Missing \"disks\" in json configuration"
        raise ConfigurationException(failMessage)

    if "lvm" in config:
        print("Configuring LVM")
        lvm(config["lvm"])

    if "format" in config:
        print("Formatting disks")
        for f in config["format"]:
            print("Formatting {0} as {1}".format(f["path"], f["format"]))
            formatPartition(f)
    else:
        failMessage = "Missing \"format\" in json configuration"
        raise ConfigurationException(failMessage)

    if "mount" in config:
        print("Mounting drives")
        for m in config["mount"]:
            print("Mounting {0} to {1}".format(m["device"], m["path"]))
            mount(m)
    else:
        failMessage = "Missing \"mount\" in json configuration"
        raise ConfigurationException(failMessage)

    if "packages" in config:
        print("Performing pacstrap on /mnt")
        pacstrap(config["packages"])
    else:
        failMessage = "Missing \"pacstrap\" in json configuration"

    if "services" in config:
        print("Enabling services")
        enableServices(config["services"])

    if "hostname" in config:
        print("Setting hostname to {0}".format(config["hostname"]))
        setHostname(config["hostname"])

    if "timezone" in config:
        print("Setting timezone to {0}".format(config["timezone"]))
        setTimezone(config["timezone"])

    if "localization" in config:
        print("Setting localization")
        setLocalization(config["localization"])

    if "environment" in config:
        print("Configuring /etc/environment")
        envVariables(config["environment"])

    if "users" in config:
        print("Creating Users")
        for user in config["users"]:
            createUser(user)

    setWheelSudo()
    genFstab()

    if "hosts" in config:
        print("Configuring /etc/hosts")
        setHosts(config["hosts"])

    if "bootloader" in config:
        print("Configuring bootloader")
        setBootLoader(config["bootloader"])

main()
