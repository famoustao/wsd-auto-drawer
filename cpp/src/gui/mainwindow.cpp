#include "mainwindow.h"
#include "ui_mainwindow.h"
#include "converter.h"
#include <QFileDialog>
#include <QMessageBox>
#include <QDesktopServices>
#include <QUrl>
#include <QDir>
#include <QFileInfo>

ConverterWorker::ConverterWorker(Mode mode, const QStringList& inputs,
                                  const QString& outputDir, const QString& templatePath,
                                  QObject* parent)
    : QThread(parent), m_mode(mode), m_inputs(inputs),
      m_outputDir(outputDir), m_templatePath(templatePath) {}

void ConverterWorker::run() {
    int success = 0, failed = 0;
    QString ext = (m_mode == Svg2Wsd) ? ".wsd" : ".svg";

    for (int i = 0; i < m_inputs.size() && !m_stop; ++i) {
        QString input = m_inputs[i];
        QString base = QFileInfo(input).baseName();
        QString output = m_outputDir + "/" + base + ext;

        emit progress(i + 1, m_inputs.size(), QFileInfo(input).fileName());

        try {
            if (m_mode == Svg2Wsd) {
                converter::svgToWsd(m_templatePath.toStdString(),
                                    input.toStdString(),
                                    output.toStdString());
            } else {
                converter::wsdToSvg(input.toStdString(), output.toStdString());
            }
            emit log("[OK] " + QFileInfo(input).fileName());
            ++success;
        } catch (...) {
            emit log("[FAIL] " + QFileInfo(input).fileName());
            ++failed;
        }
    }

    emit finished(success, failed, m_inputs.size());
}

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent), ui(new Ui::MainWindow) {
    ui->setupUi(this);
    setWindowTitle("WSD Auto Drawer - C++ (Template Mode)");

    connect(ui->btnBrowseInput, &QPushButton::clicked, this, &MainWindow::onBrowseInput);
    connect(ui->btnBrowseOutput, &QPushButton::clicked, this, &MainWindow::onBrowseOutput);
    connect(ui->btnConvert, &QPushButton::clicked, this, &MainWindow::onConvert);
}

MainWindow::~MainWindow() {
    delete ui;
}

void MainWindow::onBrowseInput() {
    bool batch = ui->checkBatch->isChecked();
    int mode = ui->comboMode->currentIndex();
    QString filter = (mode == 0) ? "SVG Files (*.svg)" : "WSD Files (*.wsd)";

    if (batch) {
        QString dir = QFileDialog::getExistingDirectory(this, "选择输入文件夹");
        if (!dir.isEmpty()) ui->editInput->setText(dir);
    } else {
        QStringList files = QFileDialog::getOpenFileNames(this, "选择文件", QString(), filter);
        if (!files.isEmpty()) ui->editInput->setText(files.join(";"));
    }
}

void MainWindow::onBrowseOutput() {
    QString dir = QFileDialog::getExistingDirectory(this, "选择输出文件夹");
    if (!dir.isEmpty()) ui->editOutput->setText(dir);
}

void MainWindow::onConvert() {
    QString inputRaw = ui->editInput->text().trimmed();
    QString outputDir = ui->editOutput->text().trimmed();
    int modeIdx = ui->comboMode->currentIndex();

    if (inputRaw.isEmpty()) {
        QMessageBox::warning(this, "警告", "请选择输入文件或文件夹");
        return;
    }

    // SVG -> WSD 模式需要模板文件
    QString templatePath;
    if (modeIdx == 0) {
        templatePath = QFileDialog::getOpenFileName(
            this, "选择 WSD 模板文件", QString(),
            "WSD Files (*.wsd)");
        if (templatePath.isEmpty()) {
            QMessageBox::warning(this, "警告",
                "SVG 转 WSD 需要一个模板文件。\n"
                "请选择一个能被 EduEditor 正常打开的 .wsd 文件作为模板。\n\n"
                "转换后的文件将保留模板的文档结构，仅替换矢量坐标数据。");
            return;
        }
    }

    if (outputDir.isEmpty()) {
        outputDir = QDir(inputRaw).absolutePath();
        ui->editOutput->setText(outputDir);
    }

    QStringList inputs;
    if (inputRaw.contains(";")) {
        inputs = inputRaw.split(";");
    } else if (QFileInfo(inputRaw).isDir()) {
        QString ext = (modeIdx == 0) ? ".svg" : ".wsd";
        QDir dir(inputRaw);
        for (const auto& f : dir.entryList(QDir::Files)) {
            if (f.endsWith(ext, Qt::CaseInsensitive)) inputs.append(dir.absoluteFilePath(f));
        }
    } else {
        inputs.append(inputRaw);
    }

    if (inputs.isEmpty()) {
        QMessageBox::warning(this, "警告", "未找到有效文件");
        return;
    }

    ui->btnConvert->setEnabled(false);
    ui->progressBar->setMaximum(inputs.size());
    ui->progressBar->setValue(0);
    ui->textLog->clear();

    auto mode = (modeIdx == 0) ? ConverterWorker::Svg2Wsd : ConverterWorker::Wsd2Svg;
    m_worker = new ConverterWorker(mode, inputs, outputDir, templatePath, this);
    connect(m_worker, &ConverterWorker::log, this, &MainWindow::onLog);
    connect(m_worker, &ConverterWorker::progress, this, &MainWindow::onProgress);
    connect(m_worker, &ConverterWorker::finished, this, &MainWindow::onFinished);
    m_worker->start();
}

void MainWindow::onLog(const QString& msg) {
    ui->textLog->append(msg);
}

void MainWindow::onProgress(int current, int total, const QString& file) {
    ui->progressBar->setValue(current);
    ui->labelStatus->setText(QString("处理中: %1/%2 - %3").arg(current).arg(total).arg(file));
}

void MainWindow::onFinished(int success, int failed, int total) {
    ui->btnConvert->setEnabled(true);
    ui->labelStatus->setText(QString("完成: 成功 %1 / 失败 %2 / 总计 %3").arg(success).arg(failed).arg(total));

    QMessageBox::information(this, "完成",
        QString("转换完成!\n成功: %1\n失败: %2\n总计: %3").arg(success).arg(failed).arg(total));
}
