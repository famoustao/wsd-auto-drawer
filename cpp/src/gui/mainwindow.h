#pragma once
#include <QMainWindow>
#include <QThread>
#include <atomic>

QT_BEGIN_NAMESPACE
namespace Ui { class MainWindow; }
QT_END_NAMESPACE

class ConverterWorker : public QThread {
    Q_OBJECT
public:
    enum Mode { Svg2Wsd, Wsd2Svg };
    ConverterWorker(Mode mode, const QStringList& inputs, const QString& outputDir, QObject* parent = nullptr);
    void run() override;
    void stop() { m_stop = true; }

signals:
    void progress(int current, int total, const QString& file);
    void log(const QString& msg);
    void finished(int success, int failed, int total);

private:
    Mode m_mode;
    QStringList m_inputs;
    QString m_outputDir;
    std::atomic<bool> m_stop{false};
};

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow(QWidget* parent = nullptr);
    ~MainWindow();

private slots:
    void onBrowseInput();
    void onBrowseOutput();
    void onConvert();
    void onLog(const QString& msg);
    void onProgress(int current, int total, const QString& file);
    void onFinished(int success, int failed, int total);

private:
    Ui::MainWindow* ui;
    ConverterWorker* m_worker = nullptr;
};
